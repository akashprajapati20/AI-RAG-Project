"""Shared Gemini API client."""

from functools import lru_cache

from google import genai
from google.genai import types

from app.config import get_settings

# Gemini returns 429 (rate limit) and 503 (overloaded) under load; retry those with exponential backoff.
_RETRY = types.HttpRetryOptions(
    attempts=6,
    initial_delay=2.0,
    max_delay=60.0,
    http_status_codes=[429, 500, 502, 503, 504],
)


@lru_cache
def get_client() -> genai.Client:
    settings = get_settings()
    if not settings.google_api_key:
        raise RuntimeError("GOOGLE_API_KEY is not set. Add it to the .env file in the project root.")
    return genai.Client(api_key=settings.google_api_key, http_options=types.HttpOptions(retry_options=_RETRY))
