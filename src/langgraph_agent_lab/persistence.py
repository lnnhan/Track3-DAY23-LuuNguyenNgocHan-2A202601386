"""Checkpointer adapter."""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from typing import Any

# Default database path
DEFAULT_DB_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "data", "checkpoints.db")


def build_checkpointer(kind: str = "memory", database_url: str | None = None) -> Any | None:
    """Return a LangGraph checkpointer.

    Supported kinds:
    - "none": No checkpointer (stateless)
    - "memory": In-memory checkpointer (MemorySaver)
    - "sqlite": SQLite checkpointer with persistence

    For SQLite:
    - Uses langgraph-checkpoint-sqlite SqliteSaver
    - Connects via sqlite3.connect() with WAL mode
    - Database path from CHECKPOINT_DB_PATH env var or default
    """
    if kind == "none":
        return None

    if kind == "memory":
        from langgraph.checkpoint.memory import MemorySaver

        return MemorySaver()

    if kind == "sqlite":
        try:
            from langgraph.checkpoint.sqlite import SqliteSaver
        except ImportError as exc:
            raise RuntimeError(
                "Install langgraph-checkpoint-sqlite: pip install langgraph-checkpoint-sqlite"
            ) from exc

        db_path = database_url or os.environ.get("CHECKPOINT_DB_PATH", DEFAULT_DB_PATH)

        # Ensure directory exists
        db_dir = os.path.dirname(db_path)
        if db_dir:
            Path(db_dir).mkdir(parents=True, exist_ok=True)

        # Create connection with check_same_thread=False for LangGraph compatibility
        conn = sqlite3.connect(db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row

        # Enable WAL mode for better concurrent access
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.commit()

        # Return SqliteSaver with the connection
        return SqliteSaver(conn=conn)

    if kind == "postgres":
        try:
            from langgraph.checkpoint.postgres import PostgresSaver
        except ImportError as exc:
            raise RuntimeError(
                "Install langgraph-checkpoint-postgres: pip install langgraph-checkpoint-postgres"
            ) from exc

        conn_string = database_url or os.environ.get("DATABASE_URL")
        if not conn_string:
            raise ValueError(
                "Postgres checkpointer requires DATABASE_URL or database_url parameter"
            )

        # Create PostgresSaver
        saver = PostgresSaver.from_conn_string(conn_string)
        saver.setup()  # Create tables if not exist
        return saver

    raise ValueError(f"Unknown checkpointer kind: {kind}")


def get_checkpointer_info(checkpointer: Any) -> dict[str, Any]:
    """Get information about a checkpointer for debugging/display.

    Returns dict with:
    - type: checkpointer type (memory, sqlite, postgres)
    - connected: whether checkpointer is ready
    - metadata: type-specific information
    """
    info = {"type": "unknown", "connected": False, "metadata": {}}

    if checkpointer is None:
        info["type"] = "none"
        info["connected"] = False
        return info

    checkpointer_type = type(checkpointer).__name__

    if "Memory" in checkpointer_type:
        info["type"] = "memory"
        info["connected"] = True
        info["metadata"] = {"description": "In-memory checkpointer (stateless across restarts)"}

    elif "Sqlite" in checkpointer_type or "SQLite" in checkpointer_type:
        info["type"] = "sqlite"
        info["connected"] = True
        info["metadata"] = {"description": "SQLite checkpointer with persistence"}

    elif "Postgres" in checkpointer_type:
        info["type"] = "postgres"
        info["connected"] = True
        info["metadata"] = {"description": "PostgreSQL checkpointer"}

    return info
