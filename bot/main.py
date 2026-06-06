from __future__ import annotations

import asyncio
import datetime as dt
import logging
import random
import re
import tempfile
import threading
from html import escape
from pathlib import Path

import pytz
from telegram import BotCommand, Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from bot.config import get_settings
from bot.db import Database
from bot.services.conversation import ConversationService
from bot.services.events import EventService
from bot.services.local_audio import LocalWhisperTranscriber, synthesize_with_edge_tts
from bot.services.memory import MemoryService
from bot.services.camera import CAMERAS, check_clothesline, view_channel
from bot.services.weather import fetch_weather, format_weather
from bot.services.search import fetch_currency, web_search, format_for_ai as format_search
from bot.services.natural_language import AUDIO_REQUEST_WORDS, detect_intent, local_chat_reply
from bot.services.openai_assistant import OpenAIAssistant
from bot.services.reminders import ReminderService
from bot.services.studies import StudyService
from bot.services.surveillance import SurveillanceService


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

settings = get_settings()
db = Database(settings.database_path)
study_service = StudyService(db)
event_service = EventService(db)
memory_service = MemoryService(db)
reminder_service = ReminderService(db)
conversation_service = ConversationService(db)
ai = OpenAIAssistant(settings.gemini_api_key)
local_transcriber = LocalWhisperTranscriber()
surveillance = SurveillanceService(settings.timezone)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _time_aware_greeting() -> str:
    tz = pytz.timezone(settings.timezone)
    hour = dt.datetime.now(tz).hour
    if hour < 12:
        options = [
            "Bom dia, Guto. O que você precisa organizar hoje?",
            "Bom dia. Tem algo pra resolver ou só passou pra dar um oi?",
            "Bom dia. Me fala o que tá na cabeça pra hoje.",
        ]
    elif hour < 18:
        options = [
            "Boa tarde. O que precisa?",
            "Oi, Guto. Posso ajudar com alguma coisa agora?",
            "Boa tarde. Me fala o que tá rolando.",
        ]
    else:
        options = [
            "Boa noite. O que posso fazer por você agora?",
            "Boa noite, Guto. Tem algo pra organizar antes de dormir?",
            "Oi. Como posso ajudar hoje à noite?",
        ]
    return random.choice(options)


def _format_routine(memories: dict[str, str]) -> str:
    mapping = {
        "weekday_wake_window": "Acordar (dias úteis)",
        "work_departure_window": "Sair para o trabalho",
        "work_arrival": "Chegar no trabalho",
        "lunch_window": "Almoço",
        "return_home": "Volta para casa",
        "evening_planning": "Planejamento noturno",
        "church_wednesday": "Igreja (qua/sex)",
        "church_sunday": "Igreja (domingo)",
        "bible_version": "Bíblia",
        "weekend_wake_time": "Acordar (fim de semana)",
        "study_block_minutes": "Blocos de estudo",
    }
    lines = ["Sua rotina atual:"]
    for key, label in mapping.items():
        if key in memories:
            val = memories[key]
            suffix = " min" if key == "study_block_minutes" else ""
            lines.append(f"- {label}: {val}{suffix}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Reply senders
# ---------------------------------------------------------------------------

async def send_reply(update: Update, text: str) -> None:
    if len(text) <= 4000:
        await update.effective_message.reply_text(text)
        return
    # Split long messages at sentence boundaries
    for chunk in _split_text(text, 4000):
        await update.effective_message.reply_text(chunk)


def _split_text(text: str, limit: int) -> list[str]:
    chunks, current = [], ""
    for sentence in re.split(r"(?<=[.!?])\s+", text):
        if len(current) + len(sentence) + 1 > limit:
            if current:
                chunks.append(current.strip())
            current = sentence
        else:
            current = (current + " " + sentence).strip() if current else sentence
    if current:
        chunks.append(current.strip())
    return chunks or [text[:limit]]


async def send_photo(update: Update, image_bytes: bytes, caption: str = "") -> None:
    import io
    await update.effective_message.reply_photo(
        photo=io.BytesIO(image_bytes),
        caption=caption[:1024] if caption else None,
    )


async def send_audio_reply(update: Update, text: str) -> None:
    """Send text immediately, generate and send TTS audio in background."""
    await send_reply(update, text)
    asyncio.create_task(_send_tts_background(update, text))


async def _send_tts_background(update: Update, text: str) -> None:
    loop = asyncio.get_event_loop()
    with tempfile.TemporaryDirectory() as temp_dir:
        tmp = Path(temp_dir)
        audio_path = None

        # Gemini TTS in executor — avoids blocking the event loop
        gemini_path = tmp / "resposta.wav"
        success = await loop.run_in_executor(
            None, lambda: ai.text_to_audio(text, gemini_path)
        )
        if success:
            audio_path = gemini_path

        # Fallback: Edge TTS (already async)
        if audio_path is None:
            edge_path = tmp / "resposta.mp3"
            if await synthesize_with_edge_tts(text, edge_path):
                audio_path = edge_path

        if not audio_path or not audio_path.exists() or audio_path.stat().st_size == 0:
            return
        try:
            with audio_path.open("rb") as audio_file:
                await update.effective_message.reply_audio(audio=audio_file, title="Guto")
        except Exception as exc:
            logging.warning("TTS send failed: %s", exc)


# ---------------------------------------------------------------------------
# Core reply builder
# ---------------------------------------------------------------------------

async def build_natural_reply(text: str) -> str:
    intent = detect_intent(text)
    logging.info("Detected intent=%s", intent.name)

    if intent.name == "greeting":
        return _time_aware_greeting()

    memories = memory_service.list_memories()
    history = conversation_service.get_history()

    # Routine — local response, no AI call needed
    if intent.name == "routine":
        return _format_routine(memories)

    # List intents — fetch data, delegate natural formatting to AI
    if intent.name == "list_studies":
        studies = study_service.list_studies()
        if not studies:
            action_result = "Nenhum estudo cadastrado ainda."
        else:
            items = "\n".join(
                f"  {i + 1}. {s.topic} — {s.status}, {s.category}"
                for i, s in enumerate(studies)
            )
            action_result = f"Estudos cadastrados ({len(studies)}):\n{items}"
        reply = ai.reply(text, memories, history, action_result)
        return reply or action_result

    if intent.name == "list_events":
        events = event_service.list_events()
        if not events:
            action_result = "Nenhum evento cadastrado ainda."
        else:
            items = "\n".join(
                f"  {i + 1}. {e.title}: {e.when_text}"
                for i, e in enumerate(events)
            )
            action_result = f"Eventos cadastrados ({len(events)}):\n{items}"
        reply = ai.reply(text, memories, history, action_result)
        return reply or action_result

    if intent.name == "list_reminders":
        reminders = reminder_service.list_reminders()
        if not reminders:
            action_result = "Nenhum lembrete cadastrado ainda."
        else:
            items = "\n".join(
                f"  {i + 1}. {r.title}: {r.remind_at_text}{'  ✓' if r.done else ''}"
                for i, r in enumerate(reminders)
            )
            action_result = f"Lembretes ({len(reminders)}):\n{items}"
        reply = ai.reply(text, memories, history, action_result)
        return reply or action_result

    # Create actions — do it, then let AI confirm naturally
    if intent.name == "create_study":
        study = study_service.create_study(intent.data["topic"])
        action_result = (
            f"Estudo criado: '{study.topic}' "
            f"(categoria: {study.category}, {study.minutes} min por sessão)"
        )
        reply = ai.reply(text, memories, history, action_result)
        return reply or f"Anotei o estudo: {study.topic}."

    if intent.name == "create_event":
        event = event_service.create_event(intent.data["title"], intent.data["when_text"])
        action_result = f"Evento criado: '{event.title}' para {event.when_text}"
        reply = ai.reply(text, memories, history, action_result)
        return reply or f"Evento anotado: {event.title} em {event.when_text}."

    if intent.name == "create_reminder":
        reminder = reminder_service.create_reminder(
            intent.data["title"], intent.data["when_text"]
        )
        action_result = f"Lembrete criado: '{reminder.title}' para {reminder.remind_at_text}"
        reply = ai.reply(text, memories, history, action_result)
        return reply or f"Lembrete anotado: {reminder.title}."

    # Web search
    if intent.name == "web_search":
        query = intent.data.get("query", text)
        loop = asyncio.get_event_loop()

        # Currency / financial data — use dedicated API (more accurate than DuckDuckGo)
        currency_info = await loop.run_in_executor(None, lambda: fetch_currency(query))
        if currency_info:
            reply = ai.reply(text, memories, history, action_result=f"Cotação em tempo real: {currency_info}")
            return reply or currency_info

        # General web search
        results = await loop.run_in_executor(None, lambda: web_search(query))
        search_context = format_search(query, results)
        reply = ai.reply(text, memories, history, action_result=search_context)
        return reply or "Não encontrei resultados para essa pesquisa."

    # Camera intents — handled by caller (need update object), return marker
    if intent.name in ("check_clothesline", "view_camera", "toggle_surveillance"):
        return f"__camera__{intent.name}__{intent.data.get('channel', '')}__{intent.data.get('on', '')}"

    # Generic chat (plan_week, project_chat, fallback)
    reply = ai.reply(text, memories, history)
    return reply or local_chat_reply(text)


# ---------------------------------------------------------------------------
# Command handlers
# ---------------------------------------------------------------------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = str(update.effective_chat.id)
    memory_service.set_memory("user_chat_id", chat_id)
    await send_reply(
        update,
        "Pronto, Guto. Pode falar comigo naturalmente — compromisso, estudo, lembrete ou o que vier na cabeça.",
    )


async def routine(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    memories = memory_service.list_memories()
    await send_reply(update, _format_routine(memories))


async def config(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await routine(update, context)


async def create_study(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    topic = " ".join(context.args).strip()
    if not topic:
        await send_reply(update, "Me manda assim: /estudo assunto que você precisa estudar")
        return
    study = study_service.create_study(topic)
    memories = memory_service.list_memories()
    history = conversation_service.get_history()
    action_result = (
        f"Estudo criado via comando: '{study.topic}' "
        f"(categoria: {study.category}, {study.minutes} min por sessão)"
    )
    reply = ai.reply(topic, memories, history, action_result)
    await send_reply(update, reply or f"Anotei o estudo: {study.topic}.")


async def list_studies(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    studies = study_service.list_studies()
    if not studies:
        await send_reply(update, "Você não tem estudos cadastrados ainda. Quer adicionar algum?")
        return
    lines = [f"{i + 1}. {s.topic} — {s.status}" for i, s in enumerate(studies)]
    await send_reply(update, "Seus estudos:\n" + "\n".join(lines))


async def create_event(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    raw = " ".join(context.args).strip()
    parts = [p.strip() for p in raw.split("|")]
    if len(parts) < 2:
        await send_reply(update, "Me manda assim: /evento titulo | data/hora | descrição opcional")
        return
    title, when_text = parts[0], parts[1]
    description = parts[2] if len(parts) > 2 else ""
    event = event_service.create_event(title, when_text, description)
    await send_reply(update, f"Evento criado: {event.title} em {event.when_text}.")


async def list_events(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    events = event_service.list_events()
    if not events:
        await send_reply(update, "Nenhum evento cadastrado ainda.")
        return
    lines = [f"{i + 1}. {e.title}: {e.when_text}" for i, e in enumerate(events)]
    await send_reply(update, "Seus eventos:\n" + "\n".join(lines))


async def list_reminders(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    reminders = reminder_service.list_reminders()
    if not reminders:
        await send_reply(update, "Nenhum lembrete cadastrado ainda.")
        return
    lines = [
        f"{i + 1}. {r.title}: {r.remind_at_text}{'  ✓' if r.done else ''}"
        for i, r in enumerate(reminders)
    ]
    await send_reply(update, "Seus lembretes:\n" + "\n".join(lines))


async def memories(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    data = memory_service.list_memories()
    lines = [f"- {k}: {v}" for k, v in data.items() if k != "user_chat_id"]
    await send_reply(update, "O que eu sei sobre você:\n" + "\n".join(lines))


# ---------------------------------------------------------------------------
# Message handlers
# ---------------------------------------------------------------------------

async def _bg_clothesline(update: Update) -> None:
    """Background task: capture clothesline cameras and send analysis."""
    loop = asyncio.get_event_loop()
    try:
        text_resp, images = await loop.run_in_executor(
            None, lambda: check_clothesline(ai._client, settings.rtsp_base_url)
        )
        for img in images:
            await send_photo(update, img)
        await send_audio_reply(update, text_resp)
        conversation_service.add_message("assistant", f"[análise do varal] {text_resp}")
    except Exception as exc:
        logging.warning("Clothesline background task failed: %s", exc)
        await send_reply(update, "Não consegui verificar o varal agora.")


async def _bg_view_camera(update: Update, channel: int) -> None:
    """Background task: capture a single channel and send description."""
    loop = asyncio.get_event_loop()
    try:
        description, frame = await loop.run_in_executor(
            None, lambda: view_channel(ai._client, settings.rtsp_base_url, channel)
        )
        if frame:
            await send_photo(update, frame, caption=description)
        else:
            await send_reply(update, description)
    except Exception as exc:
        logging.warning("View camera background task failed: %s", exc)
        await send_reply(update, "Não consegui capturar a câmera agora.")


async def _handle_camera_reply(update: Update, reply: str) -> bool:
    """Handle camera marker replies. Returns True if handled."""
    if not reply.startswith("__camera__"):
        return False
    parts = reply.split("__")
    intent_name = parts[2] if len(parts) > 2 else ""
    channel_str = parts[3] if len(parts) > 3 else ""
    on_str = parts[4] if len(parts) > 4 else ""

    if not settings.rtsp_base_url:
        await send_reply(update, "A URL das câmeras não está configurada no .env (RTSP_URL).")
        return True

    if intent_name == "check_clothesline":
        await send_reply(update, "Verificando o varal, um segundo...")
        asyncio.create_task(_bg_clothesline(update))

    elif intent_name == "view_camera":
        channel = int(channel_str) if channel_str.isdigit() else 3
        cam = CAMERAS.get(channel)
        cam_name = cam.name if cam else f"Canal {channel}"
        await send_reply(update, f"Capturando {cam_name}...")
        asyncio.create_task(_bg_view_camera(update, channel))

    elif intent_name == "toggle_surveillance":
        surveillance.enabled = on_str == "true"
        state = "ativada" if surveillance.enabled else "desativada"
        await send_reply(update, f"Vigilância automática {state}.")

    return True


async def free_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = update.message.text or ""
    logging.info("Text message from chat_id=%s", update.effective_chat.id)
    conversation_service.add_message("user", text)
    reply = await build_natural_reply(text)
    if await _handle_camera_reply(update, reply):
        return
    conversation_service.add_message("assistant", reply)
    logging.info("Reply sent: %r", reply[:120])
    lowered = text.strip().lower()
    if "audio" in lowered or "áudio" in lowered:
        await send_audio_reply(update, reply)
    else:
        await send_reply(update, reply)


async def voice_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    logging.info("Audio message from chat_id=%s", update.effective_chat.id)
    audio = update.message.voice or update.message.audio
    if not audio:
        await send_reply(update, "Recebi o áudio, mas não consegui acessar o arquivo.")
        return

    with tempfile.TemporaryDirectory() as temp_dir:
        suffix = ".ogg" if update.message.voice else ".mp3"
        audio_path = Path(temp_dir) / f"entrada{suffix}"
        telegram_file = await context.bot.get_file(audio.file_id)
        await telegram_file.download_to_drive(custom_path=audio_path)

        transcript = ""

        # Try Gemini transcription first
        if ai.is_ready():
            try:
                transcript = ai.transcribe_audio(audio_path)
            except Exception as exc:
                logging.warning("Gemini transcription failed: %s", type(exc).__name__)

        # Fallback to local Whisper (works even without OpenAI key)
        if not transcript:
            try:
                transcript = local_transcriber.transcribe(audio_path)
            except Exception as exc:
                logging.warning("Local transcription failed: %s", type(exc).__name__)

    if not transcript:
        await send_reply(update, "Não consegui entender o áudio. Pode mandar em texto?")
        return

    # Process exactly like a text message — transcript never shown to user
    logging.info("Transcript: %r", transcript)
    conversation_service.add_message("user", f"[áudio] {transcript}")
    reply = await build_natural_reply(transcript)
    if await _handle_camera_reply(update, reply):
        return
    conversation_service.add_message("assistant", reply)
    await send_audio_reply(update, reply)


async def unsupported_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await send_reply(
        update,
        "Entendo texto e áudio. Para outros tipos de arquivo ainda preciso evoluir.",
    )


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logging.exception("Handler error: %s", context.error)
    if isinstance(update, Update) and update.effective_message:
        await update.effective_message.reply_text(
            f"Tive um erro interno: {escape(type(context.error).__name__)}. Já anotei pra ajustar."
        )


# ---------------------------------------------------------------------------
# Scheduled jobs
# ---------------------------------------------------------------------------

async def check_reminders(context: ContextTypes.DEFAULT_TYPE) -> None:
    tz = pytz.timezone(settings.timezone)
    now = dt.datetime.now(tz).strftime("%Y-%m-%d %H:%M:%S")
    chat_id_str = memory_service.list_memories().get("user_chat_id")
    if not chat_id_str:
        return

    due = reminder_service.get_due_reminders(now)
    for reminder in due:
        try:
            await context.bot.send_message(
                chat_id=int(chat_id_str),
                text=f"Lembrete: {reminder.title}",
            )
            reminder_service.mark_done(reminder.id)
        except Exception as exc:
            logging.warning("Failed to send reminder %s: %s", reminder.id, exc)


async def surveillance_check(context: ContextTypes.DEFAULT_TYPE) -> None:
    if not settings.rtsp_base_url:
        return
    chat_id_str = memory_service.list_memories().get("user_chat_id")
    if not chat_id_str:
        return

    async def send_alert(channel: int, description: str, image_bytes: bytes) -> None:
        import io
        cam = CAMERAS.get(channel)
        cam_name = cam.name if cam else f"Canal {channel}"
        caption = f"Movimento detectado — {cam_name}\n{description}"
        await context.bot.send_photo(
            chat_id=int(chat_id_str),
            photo=io.BytesIO(image_bytes),
            caption=caption[:1024],
        )

    await surveillance.run_check(ai._client, settings.rtsp_base_url, send_alert)


async def morning_briefing(context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id_str = memory_service.list_memories().get("user_chat_id")
    if not chat_id_str:
        return

    tz = pytz.timezone(settings.timezone)
    now = dt.datetime.now(tz)
    weekday_names = [
        "Segunda-feira", "Terça-feira", "Quarta-feira",
        "Quinta-feira", "Sexta-feira", "Sábado", "Domingo",
    ]
    weekday = weekday_names[now.weekday()]

    events = event_service.list_events(limit=5)
    pending_reminders = [r for r in reminder_service.list_reminders(limit=10) if not r.done]

    loop = asyncio.get_event_loop()
    weather_data = await loop.run_in_executor(None, fetch_weather)
    weather_text = format_weather(weather_data)

    memories = memory_service.list_memories()
    briefing = ai.generate_morning_briefing(
        memories,
        events=[f"{e.title}: {e.when_text}" for e in events],
        reminders=[r.title for r in pending_reminders[:5]],
        weekday=weekday,
        weather=weather_text,
    )
    if briefing:
        try:
            await context.bot.send_message(chat_id=int(chat_id_str), text=briefing)
        except Exception as exc:
            logging.warning("Failed to send morning briefing: %s", exc)


# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

async def configure_bot_profile(app: Application) -> None:
    description = (
        "Assistente pessoal do Guto — agenda, estudos, projetos, lembretes e rotina. "
        "Fale por texto ou envie um áudio."
    )
    await app.bot.set_my_description(description)
    await app.bot.set_my_short_description("Agenda, estudos, rotina e lembretes.")
    await app.bot.set_my_commands(
        [
            BotCommand("inicio", "Começar"),
            BotCommand("rotina", "Ver rotina"),
            BotCommand("estudos", "Ver estudos"),
            BotCommand("eventos", "Ver eventos"),
            BotCommand("lembretes", "Ver lembretes"),
            BotCommand("memoria", "Ver memórias"),
        ]
    )


def build_app() -> Application:
    if not settings.telegram_bot_token:
        raise RuntimeError("Configure TELEGRAM_BOT_TOKEN no arquivo .env.")

    db.initialize()

    # Pre-load Whisper model in background to avoid cold-start delay on first audio
    threading.Thread(target=local_transcriber.preload, daemon=True).start()

    app = (
        Application.builder()
        .token(settings.telegram_bot_token)
        .post_init(configure_bot_profile)
        .build()
    )

    # Commands
    app.add_handler(CommandHandler(["inicio", "start"], start))
    app.add_handler(CommandHandler(["rotina", "config"], routine))
    app.add_handler(CommandHandler("estudo", create_study))
    app.add_handler(CommandHandler("estudos", list_studies))
    app.add_handler(CommandHandler("evento", create_event))
    app.add_handler(CommandHandler("eventos", list_events))
    app.add_handler(CommandHandler("lembretes", list_reminders))
    app.add_handler(CommandHandler("memoria", memories))

    # Message handlers
    app.add_handler(MessageHandler((filters.VOICE | filters.AUDIO) & ~filters.COMMAND, voice_message))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, free_text))
    app.add_handler(MessageHandler(filters.ALL, unsupported_message))
    app.add_error_handler(error_handler)

    # Scheduled jobs
    tz = pytz.timezone(settings.timezone)
    app.job_queue.run_repeating(check_reminders, interval=60, first=10)
    if settings.rtsp_base_url:
        app.job_queue.run_repeating(surveillance_check, interval=600, first=60)
        logging.info("Vigilância de câmeras ativada (canal 3, 5, 7, 8)")
    app.job_queue.run_daily(
        morning_briefing,
        time=dt.time(5, 45, tzinfo=tz),
        days=(0, 1, 2, 3, 4),  # Mon–Fri
    )
    app.job_queue.run_daily(
        morning_briefing,
        time=dt.time(9, 30, tzinfo=tz),
        days=(5, 6),  # Sat–Sun
    )

    return app


def main() -> None:
    app = build_app()
    app.run_polling()


if __name__ == "__main__":
    main()
