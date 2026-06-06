from __future__ import annotations

from bot.db import Database


class MemoryService:
    def __init__(self, db: Database) -> None:
        self.db = db

    def list_memories(self) -> dict[str, str]:
        with self.db.connect() as conn:
            rows = conn.execute(
                "SELECT key, value FROM memories ORDER BY key"
            ).fetchall()
        return {row["key"]: row["value"] for row in rows}

    def set_memory(self, key: str, value: str) -> None:
        with self.db.connect() as conn:
            conn.execute(
                """
                INSERT INTO memories (key, value)
                VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    value = excluded.value,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (key, value),
            )

