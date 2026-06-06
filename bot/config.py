from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

try:
    from dotenv import load_dotenv
except ModuleNotFoundError:
    load_dotenv = None


if load_dotenv:
    load_dotenv()


@dataclass(frozen=True)
class Settings:
    telegram_bot_token: str
    gemini_api_key: str
    database_path: Path
    timezone: str
    rtsp_base_url: str
    google_credentials_path: str
    google_api_key: str
    google_client_id: str
    google_client_secret: str
    google_token_path: str


def get_settings() -> Settings:
    return Settings(
        telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN", ""),
        gemini_api_key=os.getenv("GEMINI_API_KEY", ""),
        database_path=Path(os.getenv("DATABASE_PATH", "assistant.db")),
        timezone=os.getenv("TIMEZONE", "America/Sao_Paulo"),
        rtsp_base_url=os.getenv("RTSP_URL", ""),
        google_credentials_path=os.getenv("GOOGLE_CREDENTIALS_PATH", ""),
        google_api_key=os.getenv("GOOGLE_API_KEY", ""),
        google_client_id=os.getenv("GOOGLE_CLIENT_ID", ""),
        google_client_secret=os.getenv("GOOGLE_CLIENT_SECRET", ""),
        google_token_path=os.getenv("GOOGLE_TOKEN_PATH", "google_token.json"),
    )


DEFAULT_ROUTINE = {
    "weekday_wake_window": "5:30-6:00",
    "weekday_morning_summary": "5:45",
    "work_departure_window": "7:20-7:30",
    "work_arrival": "8:30",
    "lunch_window": "12:00-13:30",
    "return_home": "17:00",
    "study_block_minutes": "90",
    "evening_planning": "18:10",
    "church_wednesday": "19:40",
    "church_friday": "19:40",
    "weekend_wake_time": "9:00",
    "weekend_morning_summary": "9:30",
    "church_sunday": "18:00",
    "bible_version": "Almeida Corrigida",
    "calendar_creation": "automatic",
    "hourly_updates": "only_when_relevant",
}
