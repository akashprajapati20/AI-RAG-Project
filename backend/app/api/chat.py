"""Chat with the agent: plain JSON or a Server-Sent Events stream, plus conversation history."""

from collections.abc import Iterator
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request
from fastapi.sse import EventSourceResponse, ServerSentEvent
from langchain_core.messages import AIMessageChunk, HumanMessage

from app.agent.trace import describe_step
from app.api.schemas import ChatMessage, ChatRequest, ChatResponse, Conversation
from app.llm import friendly_error

router = APIRouter(tags=["chat"])

ANSWER_NODES = {"generate", "respond"}  # only their tokens are the answer (others emit JSON decisions)


@router.post("/chat", response_model=ChatResponse)
def chat(body: ChatRequest, request: Request) -> ChatResponse:
    """Ask a question and wait for the whole answer."""
    graph = request.app.state.graph
    conversation_id = body.conversation_id or str(uuid4())
    try:
        state = graph.invoke({"messages": [HumanMessage(body.message)]}, _config(conversation_id))
    except Exception as e:
        raise HTTPException(status_code=502, detail=friendly_error(e)) from e
    return _response(conversation_id, state)


@router.post("/chat/stream", response_class=EventSourceResponse)
def chat_stream(body: ChatRequest, request: Request) -> Iterator[ServerSentEvent]:
    """Ask a question and receive Server-Sent Events as the agent works:

    - `meta`   {conversation_id}                         first, so the client can continue the chat
    - `step`   {node, label, ...}                        after each agent step ("Searched for …")
    - `token`  {text}                                    answer text as the model writes it
    - `answer` {conversation_id, answer, citations, …}   last: the final answer (replaces the tokens)
    - `error`  {message}                                 instead of `answer` if the run fails
    """
    graph = request.app.state.graph
    conversation_id = body.conversation_id or str(uuid4())
    config = _config(conversation_id)
    yield ServerSentEvent(event="meta", data={"conversation_id": conversation_id})
    try:
        stream = graph.stream({"messages": [HumanMessage(body.message)]}, config, stream_mode=["updates", "messages"])
        for mode, payload in stream:
            if mode == "updates":  # a node finished: {node_name: fields it changed}
                for node, changes in payload.items():
                    yield ServerSentEvent(event="step", data=describe_step(node, changes or {}))
            else:  # "messages": (chunk, metadata) for every token any model produces
                chunk, metadata = payload
                # AIMessageChunk = streamed tokens; whole AIMessages a node returns are skipped
                # (the final answer arrives in the `answer` event anyway).
                if isinstance(chunk, AIMessageChunk) and metadata.get("langgraph_node") in ANSWER_NODES and chunk.text:
                    yield ServerSentEvent(event="token", data={"text": chunk.text})
        state = graph.get_state(config).values
        yield ServerSentEvent(event="answer", data=_response(conversation_id, state).model_dump())
    except Exception as e:
        yield ServerSentEvent(event="error", data={"message": friendly_error(e)})


@router.get("/conversations/{conversation_id}", response_model=Conversation)
def get_conversation(conversation_id: str, request: Request) -> Conversation:
    """The messages of a conversation, e.g. to restore a chat after reloading the page."""
    values = request.app.state.graph.get_state(_config(conversation_id)).values
    if not values:
        raise HTTPException(status_code=404, detail="conversation not found")
    messages = [
        ChatMessage(role="user", content=m.text)
        if m.type == "human"
        else ChatMessage(role="assistant", content=m.text, citations=m.additional_kwargs.get("citations", []))
        for m in values.get("messages", [])
    ]
    return Conversation(conversation_id=conversation_id, messages=messages)


@router.delete("/conversations/{conversation_id}", status_code=204)
def delete_conversation(conversation_id: str, request: Request) -> None:
    request.app.state.checkpointer.delete_thread(conversation_id)


def _config(conversation_id: str) -> dict:
    # thread_id is how LangGraph's checkpointer keys a conversation's saved state.
    return {"configurable": {"thread_id": conversation_id}}


def _response(conversation_id: str, state: dict) -> ChatResponse:
    return ChatResponse(
        conversation_id=conversation_id,
        answer=state["answer"],
        citations=state["citations"],
        route=state["route"],
        queries=state["queries"],
    )
