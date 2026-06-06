from __future__ import annotations

from dataclasses import dataclass

from bot.db import Database


def _parse_datetime(text: str) -> str | None:
    """Parses natural language date/time (PT-BR) to ISO string, or returns None."""
    try:
        import dateparser
        parsed = dateparser.parse(
            text,
            languages=["pt"],
            settings={
                "TIMEZONE": "America/Sao_Paulo",
                "PREFER_DATES_FROM": "future",
                "DATE_ORDER": "DMY",
                "RETURN_AS_TIMEZONE_AWARE": False,
            },
        )
        if parsed:
            return parsed.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        pass
    return None


@dataclass(frozen=True)
class Event:
    id: int
    title: str
    when_text: str
    description: str


class EventService:
    def __init__(self, db: Database) -> None:
        self.db = db

    def create_event(self, title: str, when_text: str, description: str = "") -> Event:
        when_datetime = _parse_datetime(when_text)
        with self.db.connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO events (title, when_text, when_datetime, description)
                VALUES (?, ?, ?, ?)
                """,
                (title.strip(), when_text.strip(), when_datetime, description.strip()),
            )
            event_id = int(cursor.lastrowid)
        return Event(event_id, title.strip(), when_text.strip(), description.strip())

    def list_events(self, limit: int = 10) -> list[Event]:
        with self.db.connect() as conn:
            rows = conn.execute(
                """
                SELECT id, title, when_text, description
                FROM events
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [
            Event(
                id=row["id"],
                title=row["title"],
                when_text=row["when_text"],
                description=row["description"],
            )
            for row in rows
        ]
