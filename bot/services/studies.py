from __future__ import annotations

import re
from dataclasses import dataclass

from bot.db import Database


@dataclass(frozen=True)
class Study:
    id: int
    topic: str
    category: str
    status: str
    minutes: int
    notes: str


def classify_topic(topic: str) -> str:
    text = topic.lower()
    if any(word in text for word in ["api", "python", "codigo", "programacao", "oauth", "google", "bot"]):
        return "programacao"
    if any(word in text for word in ["biblia", "igreja", "versiculo", "devocional"]):
        return "biblia"
    if any(word in text for word in ["projeto", "app", "sistema"]):
        return "projeto pessoal"
    if any(word in text for word in ["trabalho", "empresa", "relatorio"]):
        return "trabalho"
    return "geral"


def clean_topic(text: str) -> str:
    cleaned = re.sub(r"^(preciso estudar|estudar|quero estudar)\s+", "", text.strip(), flags=re.I)
    return cleaned.strip(" .") or text.strip()


class StudyService:
    def __init__(self, db: Database) -> None:
        self.db = db

    def create_study(self, topic_text: str) -> Study:
        topic = clean_topic(topic_text)
        category = classify_topic(topic)
        with self.db.connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO studies (topic, category, status, minutes)
                VALUES (?, ?, 'novo', 90)
                """,
                (topic, category),
            )
            study_id = int(cursor.lastrowid)
        return Study(study_id, topic, category, "novo", 90, "")

    def list_studies(self, limit: int = 10) -> list[Study]:
        with self.db.connect() as conn:
            rows = conn.execute(
                """
                SELECT id, topic, category, status, minutes, notes
                FROM studies
                ORDER BY updated_at DESC, id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [
            Study(
                id=row["id"],
                topic=row["topic"],
                category=row["category"],
                status=row["status"],
                minutes=row["minutes"],
                notes=row["notes"],
            )
            for row in rows
        ]

    def add_log(self, study_id: int, summary: str) -> None:
        with self.db.connect() as conn:
            conn.execute(
                "INSERT INTO study_logs (study_id, summary) VALUES (?, ?)",
                (study_id, summary),
            )
            conn.execute(
                """
                UPDATE studies
                SET status = 'em estudo', updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (study_id,),
            )

