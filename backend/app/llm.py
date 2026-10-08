"""Chat models for the agent: Gemini through LangChain, which LangGraph nodes call."""

import logging
from functools import lru_cache

from langchain_core.rate_limiters import InMemoryRateLimiter
from langchain_google_genai import ChatGoogleGenerativeAI

from app.config import get_settings

# langchain-google-genai calls generate_content directly, so google-genai logs an "automatic
# function calling is not recommended" warning on every request. It doesn't apply to us.
logging.getLogger("google_genai.models").setLevel(logging.ERROR)


def get_chat_model() -> ChatGoogleGenerativeAI:
    """The model that writes answers (CHAT_MODEL)."""
    return get_model(get_settings().chat_model)


def get_fast_model() -> ChatGoogleGenerativeAI:
    """A smaller, faster model for short structured decisions: routing, grading, rewriting
    (FAST_MODEL). It also spreads usage across two per-model quotas."""
    return get_model(get_settings().fast_model)


def get_model(name: str) -> ChatGoogleGenerativeAI:
    """Any Gemini chat model by name (one shared instance per name)."""
    return _model(name)


def friendly_error(e: Exception) -> str:
    """A one-line, user-facing description of a failed agent run."""
    if "RESOURCE_EXHAUSTED" in str(e):
        return (
            "Gemini quota used up for one of the models. Wait for it to reset, choose other models "
            "via CHAT_MODEL / FAST_MODEL in .env, or enable billing on the API key."
        )
    return f"{type(e).__name__}: {str(e).splitlines()[0][:300] if str(e) else 'unexpected error'}"


@lru_cache
def _model(name: str) -> ChatGoogleGenerativeAI:
    settings = get_settings()
    rpm = settings.llm_requests_per_minute
    return ChatGoogleGenerativeAI(
        model=name,
        # Shared by every caller of this model (the instance is cached), so the limit holds overall.
        rate_limiter=InMemoryRateLimiter(requests_per_second=rpm / 60) if rpm > 0 else None,
        google_api_key=settings.google_api_key,
        # No temperature override: Google recommends keeping Gemini 3 models at their default,
        # as lower values can cause looping or degraded reasoning.
        thinking_config={"thinking_level": settings.thinking_level},
        # Few retries: they help with brief 503 overloads, but when a daily quota (429) is used
        # up, retrying only makes the user wait longer for the same error.
        max_retries=2,
        timeout=90,
    )
