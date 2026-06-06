from __future__ import annotations

from bot.db import Database


class ConversationService:
    MAX_HISTORY = 30  # 15 exchanges stored in DB

    def __init__(self, db: Database) -> None:
        self.db = db

    def add_message(self, role: str, content: str) -> None:
        with self.db.connect() as conn:
            conn.execute(
                "INSERT INTO conversation_history (role, content) VALUES (?, ?)",
                (role, content),
            )
            # Keep only the most recent MAX_HISTORY messages
            conn.execute(
                """
                DELETE FROM conversation_history WHERE id NOT IN (
                    SELECT id FROM conversation_history ORDER BY id DESC LIMIT ?
                )
                """,
                (self.MAX_HISTORY,),
            )

    def get_history(self, limit: int = 12) -> list[dict[str, str]]:
        """Returns the last `limit` messages in chronological order."""
        with self.db.connect() as conn:
            rows = conn.execute(
                "SELECT role, content FROM conversation_history ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [{"role": row["role"], "content": row["content"]} for row in reversed(rows)]

    def clear(self) -> None:
        with self.db.connect() as conn:
            conn.execute("DELETE FROM conversation_history")
