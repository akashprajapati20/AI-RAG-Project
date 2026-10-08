import json
import os

import pytest
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessageChunk

from app.api.documents import UPLOAD_DIR, safe_filename
from app.api.main import app
from app.config import get_settings


@pytest.fixture(scope="module")
def client():
    """The real app (startup runs init_schema and the Postgres checkpointer). Skips without a DB."""
    try:
        with TestClient(app) as test_client:
            yield test_client
    except Exception as e:
        pytest.skip(f"database unavailable: {e}")


def sse_events(text: str) -> list[tuple[str, dict]]:
    """Parse a text/event-stream body into (event, data) pairs."""
    events = []
    for block in text.strip().split("\n\n"):
        fields = dict(line.split(": ", 1) for line in block.splitlines() if ": " in line)
        if "event" in fields:
            events.append((fields["event"], json.loads(fields["data"])))
    return events


class FakeGraph:
    """Stands in for the agent: replays a scripted stream, so no Gemini calls are made."""

    def __init__(self, fail_with: Exception | None = None):
        self.fail_with = fail_with

    def stream(self, inputs, config, stream_mode):
        yield "updates", {"router": {"route": "direct", "query": "hi"}}
        if self.fail_with:
            raise self.fail_with
        yield "messages", (AIMessageChunk(content="Hel"), {"langgraph_node": "respond"})
        yield "messages", (AIMessageChunk(content='{"route":'), {"langgraph_node": "router"})  # not answer text
        yield "messages", (AIMessageChunk(content="lo!"), {"langgraph_node": "respond"})

    def get_state(self, config):
        class State:
            values = {"answer": "Hello!", "citations": [], "route": "direct", "queries": []}

        return State()


# ---------------------------------------------------------------- no Gemini calls


def test_safe_filename_blocks_path_traversal():
    assert safe_filename("../../app/config.py") == "config.py"
    assert safe_filename("..\\..\\evil.md") == "evil.md"
    assert safe_filename("Q3 report (final)!.pdf") == "Q3 report (final)_.pdf"
    assert safe_filename("...") == ""


def test_health(client):
    body = client.get("/health").json()
    assert body["status"] == "ok"
    assert body["documents"] > 0


def test_list_documents(client):
    documents = client.get("/documents").json()
    pricing = next(d for d in documents if d["source"].endswith("pricing_and_plans_2026.pdf"))
    assert pricing["format"] == "pdf"
    assert pricing["chunks"] > 0


def test_upload_rejects_unsupported_types(client):
    response = client.post("/documents", files=[("files", ("tool.exe", b"MZ", "application/octet-stream"))])
    assert response.json()[0]["status"] == "failed"
    assert not (UPLOAD_DIR / "tool.exe").exists()


def test_unknown_conversation_is_404(client):
    assert client.get("/conversations/does-not-exist").status_code == 404


def test_stream_sends_meta_steps_answer_tokens_then_answer(client, monkeypatch):
    monkeypatch.setattr(client.app.state, "graph", FakeGraph())
    response = client.post("/chat/stream", json={"message": "hi"})
    assert response.headers["content-type"].startswith("text/event-stream")
    events = sse_events(response.text)
    assert [e for e, _ in events] == ["meta", "step", "token", "token", "answer"]
    assert "".join(d["text"] for e, d in events if e == "token") == "Hello!"  # router JSON filtered out
    assert events[-1][1]["answer"] == "Hello!"


def test_stream_reports_failures_as_an_error_event(client, monkeypatch):
    monkeypatch.setattr(client.app.state, "graph", FakeGraph(fail_with=RuntimeError("429 RESOURCE_EXHAUSTED")))
    events = sse_events(client.post("/chat/stream", json={"message": "hi"}).text)
    assert events[-1][0] == "error"
    assert "quota" in events[-1][1]["message"]


# ---------------------------------------------------------------- embeddings (like the retrieval tests)


def test_upload_then_delete_a_document(client):
    if not get_settings().google_api_key:
        pytest.skip("GOOGLE_API_KEY not set")
    content = b"# Parking Policy\n\nVisitor parking is in zone C, next to the loading dock.\n"
    [result] = client.post("/documents", files=[("files", ("../parking_policy.md", content, "text/markdown"))]).json()
    assert result == {"filename": "parking_policy.md", "status": "added", "chunks": 1, "error": None}

    document = next(d for d in client.get("/documents").json() if d["source"] == "data/uploads/parking_policy.md")
    assert client.delete(f"/documents/{document['id']}").status_code == 204
    assert not (UPLOAD_DIR / "parking_policy.md").exists()
    assert client.delete(f"/documents/{document['id']}").status_code == 404


# ---------------------------------------------------------------- live agent (opt-in: uses Gemini quota)


@pytest.mark.skipif(os.getenv("RUN_AGENT_TESTS") != "1", reason="uses Gemini chat quota; run with RUN_AGENT_TESTS=1")
def test_follow_up_question_uses_conversation_memory(client):
    first = client.post("/chat", json={"message": "What is the API rate limit on the Growth plan?"}).json()
    second = client.post(
        "/chat", json={"message": "And on Enterprise?", "conversation_id": first["conversation_id"]}
    ).json()
    assert "3,000" in second["answer"] or "3000" in second["answer"]

    history = client.get(f"/conversations/{first['conversation_id']}").json()["messages"]
    assert [m["role"] for m in history] == ["user", "assistant", "user", "assistant"]
    assert client.delete(f"/conversations/{first['conversation_id']}").status_code == 204
    assert client.get(f"/conversations/{first['conversation_id']}").status_code == 404
