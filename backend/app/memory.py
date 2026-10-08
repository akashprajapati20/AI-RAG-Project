"""Conversation memory: LangGraph checkpoints stored in Postgres, so chats survive restarts.

After every node, LangGraph saves the agent's state for that conversation (thread_id). The next
message in the same conversation resumes from it, which is how follow-ups like "and on
Enterprise?" keep their context.
"""

import atexit
from functools import lru_cache

from langgraph.checkpoint.postgres import PostgresSaver
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from app.config import get_settings


@lru_cache
def get_checkpointer() -> PostgresSaver:
    # A separate pool from app.db's: PostgresSaver needs autocommit and dict rows, and
    # prepare_threshold=0 (no server-side prepared statements) as LangGraph recommends for pools.
    pool = ConnectionPool(
        get_settings().database_url,
        min_size=1,
        max_size=10,
        kwargs={"autocommit": True, "prepare_threshold": 0, "row_factory": dict_row},
        open=True,
    )
    atexit.register(pool.close)
    checkpointer = PostgresSaver(pool)
    checkpointer.setup()  # creates LangGraph's checkpoint tables if missing; safe to repeat
    return checkpointer
