"""Request and response bodies. FastAPI validates them and documents them at /docs."""

from typing import Literal

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    conversation_id: str | None = Field(None, description="omit to start a new conversation")


class Citation(BaseModel):
    n: int = Field(description="the number used in the answer, as in [n]")
    title: str
    source: str
    citation: str = Field(description='e.g. "Tally Pricing and Plans 2026 › 4. SLA credits (p. 1)"')
    content: str = Field(description="the passage the answer relied on")


class ChatResponse(BaseModel):
    conversation_id: str
    answer: str
    citations: list[Citation]
    route: str = Field(description="retrieve | tools | direct")
    queries: list[str] = Field(description="search queries the agent ran")


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str
    citations: list[Citation] = []


class Conversation(BaseModel):
    conversation_id: str
    messages: list[ChatMessage]


class DocumentInfo(BaseModel):
    id: int
    title: str
    source: str
    format: str | None
    pages: int | None
    chunks: int
    ingested_at: str | None


class UploadResult(BaseModel):
    filename: str
    status: str = Field(description="added | updated | unchanged | failed")
    chunks: int = 0
    error: str | None = None
