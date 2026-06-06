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
class Reminder:
    id: int
    title: str
    remind_at_text: str
    done: bool


class ReminderService:
    def __init__(self, db: Database) -> None:
        self.db = db

    def create_reminder(self, title: str, remind_at_text: str) -> Reminder:
        when_datetime = _parse_datetime(remind_at_text)
        with self.db.connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO reminders (title, remind_at_text, remind_at_datetime)
                VALUES (?, ?, ?)
                """,
                (title.strip(), remind_at_text.strip(), when_datetime),
            )
            reminder_id = int(cursor.lastrowid)
        return Reminder(reminder_id, title.strip(), remind_at_text.strip(), False)

    def list_reminders(self, limit: int = 10) -> list[Reminder]:
        with self.db.connect() as conn:
            rows = conn.execute(
                """
                SELECT id, title, remind_at_text, done
                FROM reminders
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [
            Reminder(
                id=row["id"],
                title=row["title"],
                remind_at_text=row["remind_at_text"],
                done=bool(row["done"]),
            )
            for row in rows
        ]

    def get_due_reminders(self, now: str) -> list[Reminder]:
        """Returns pending reminders whose scheduled datetime has passed."""
        with self.db.connect() as conn:
            rows = conn.execute(
                """
                SELECT id, title, remind_at_text, done
                FROM reminders
                WHERE done = 0
                  AND remind_at_datetime IS NOT NULL
                  AND remind_at_datetime <= ?
                """,
                (now,),
            ).fetchall()
        return [
            Reminder(
                id=row["id"],
                title=row["title"],
                remind_at_text=row["remind_at_text"],
                done=bool(row["done"]),
            )
            for row in rows
        ]

    def mark_done(self, reminder_id: int) -> None:
        with self.db.connect() as conn:
            conn.execute(
                "UPDATE reminders SET done = 1 WHERE id = ?",
                (reminder_id,),
            )
