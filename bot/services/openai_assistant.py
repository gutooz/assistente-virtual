from __future__ import annotations

import logging
from pathlib import Path

from google import genai
from google.genai import types


def _build_system_prompt(memories: dict[str, str]) -> str:
    routine_labels = {
        "weekday_wake_window": "Acorda (dias úteis)",
        "work_departure_window": "Sai para o trabalho",
        "work_arrival": "Chega no trabalho",
        "lunch_window": "Almoço",
        "return_home": "Volta para casa",
        "evening_planning": "Planejamento noturno",
        "church_wednesday": "Igreja (qua/sex)",
        "church_sunday": "Igreja (domingo)",
        "bible_version": "Bíblia",
        "weekend_wake_time": "Acorda (fim de semana)",
        "study_block_minutes": "Blocos de estudo (min)",
    }

    routine_lines = [
        f"  - {label}: {memories[key]}"
        for key, label in routine_labels.items()
        if key in memories
    ]
    extra_lines = [
        f"  - {key}: {value}"
        for key, value in memories.items()
        if key not in routine_labels and key != "user_chat_id" and not key.startswith("_")
    ]

    context_parts = []
    if routine_lines:
        context_parts.append("Rotina configurada:\n" + "\n".join(routine_lines))
    if extra_lines:
        context_parts.append("Dados adicionais:\n" + "\n".join(extra_lines))

    context_text = "\n\n".join(context_parts) or "  Sem informações configuradas ainda."

    return f"""Você é o assistente pessoal do Gustavo (Guto), integrado ao Telegram.

IDENTIDADE:
Assistente executivo — direto, inteligente, proativo, humano.
Fale português brasileiro natural, como um parceiro de confiança, não como um bot.

SOBRE O GUSTAVO:
{context_text}

CAPACIDADES (não negue estas):
- Você ENVIA respostas em áudio — qualquer resposta sua é convertida automaticamente em voz pelo sistema
- Quando o Guto pedir "me manda um áudio", "explica falando" ou similar, apenas responda o conteúdo normalmente
- Você acessa câmeras da casa e analisa imagens em tempo real
- Você gerencia agenda, lembretes, estudos e projetos
- Você faz pesquisas na internet em tempo real — quando receber [Resultados da web para ...], resuma as informações de forma clara e direta, citando as fontes relevantes

ESTILO:
- Respostas curtas e objetivas (máximo 3 parágrafos curtos)
- Nunca comece com "Claro!", "Certamente!", "Com prazer!" ou similares
- Sem markdown desnecessário (sem **, __ ou # no texto)
- Tom conversacional e natural, não corporativo

REGRAS:
1. Lembrete ou evento sem horário específico → pergunte o horário ao final da resposta
2. Após ação concluída → sugira UMA próxima ação complementar, só se fizer sentido real
3. Use o histórico da conversa para entender referências como "isso", "aquele projeto", "ele"
4. Áudios → processe e responda diretamente, nunca mostre ou mencione a transcrição
5. Quando o usuário mencionar projetos ou pessoas novas → use esse contexto nas respostas seguintes
6. Dúvidas → pergunte de forma direta e curta, sem rodeios
7. Quando receber [AÇÃO EXECUTADA: ...] no contexto, confirme de forma natural e sugira próximo passo se fizer sentido"""


def _convert_history(history: list[dict[str, str]]) -> list[dict]:
    """Converts internal history to Gemini format (role: user/model, parts: list of text)."""
    converted: list[dict] = []
    for msg in history:
        role = "model" if msg["role"] == "assistant" else "user"
        if not converted and role == "model":
            continue  # Gemini history must start with user turn
        if converted and converted[-1]["role"] == role:
            converted[-1]["parts"][0]["text"] += "\n" + msg["content"]
        else:
            converted.append({"role": role, "parts": [{"text": msg["content"]}]})
    return converted


def _audio_mime(audio_path: Path) -> str:
    return {
        ".ogg": "audio/ogg",
        ".mp3": "audio/mpeg",
        ".wav": "audio/wav",
        ".m4a": "audio/mp4",
        ".webm": "audio/webm",
    }.get(audio_path.suffix.lower(), "audio/ogg")


class OpenAIAssistant:
    """AI assistant backed by Google Gemini. Class name kept for minimal code changes."""

    MODEL = "gemini-2.5-flash"

    def __init__(self, api_key: str) -> None:
        if api_key:
            self._client = genai.Client(api_key=api_key)
        else:
            self._client = None

    def is_ready(self) -> bool:
        return self._client is not None

    def _config(self, memories: dict[str, str], **kwargs) -> types.GenerateContentConfig:
        return types.GenerateContentConfig(
            system_instruction=_build_system_prompt(memories),
            max_output_tokens=1500,
            temperature=0.75,
            **kwargs,
        )

    def reply(
        self,
        user_text: str,
        memories: dict[str, str],
        history: list[dict[str, str]] | None = None,
        action_result: str = "",
    ) -> str:
        if not self._client:
            return ""
        try:
            content = user_text
            if action_result:
                content = f"{user_text}\n\n[AÇÃO EXECUTADA: {action_result}]"

            gemini_history = _convert_history(history or [])

            if gemini_history:
                chat = self._client.chats.create(
                    model=self.MODEL,
                    history=gemini_history,
                    config=self._config(memories),
                )
                response = chat.send_message(content)
            else:
                response = self._client.models.generate_content(
                    model=self.MODEL,
                    contents=content,
                    config=self._config(memories),
                )

            return response.text.strip()
        except Exception as exc:
            logging.warning("Gemini reply failed: %s", exc)
            return ""

    def transcribe_audio(self, audio_path: Path) -> str:
        if not self._client:
            return ""
        audio_file = None
        try:
            audio_file = self._client.files.upload(
                file=str(audio_path),
                config=types.UploadFileConfig(mime_type=_audio_mime(audio_path)),
            )
            response = self._client.models.generate_content(
                model=self.MODEL,
                contents=[
                    "Transcreva exatamente o que foi dito neste áudio em português brasileiro. "
                    "Retorne apenas a transcrição, sem nenhum comentário adicional.",
                    audio_file,
                ],
            )
            return response.text.strip()
        except Exception as exc:
            logging.warning("Gemini transcription failed: %s", exc)
            return ""
        finally:
            if audio_file:
                try:
                    self._client.files.delete(name=audio_file.name)
                except Exception:
                    pass

    def text_to_audio(self, text: str, output_path: Path) -> bool:
        if not self._client:
            return False
        try:
            import wave
            response = self._client.models.generate_content(
                model="gemini-2.5-flash-preview-tts",
                contents=text[:4000],
                config=types.GenerateContentConfig(
                    response_modalities=["AUDIO"],
                    speech_config=types.SpeechConfig(
                        voice_config=types.VoiceConfig(
                            prebuilt_voice_config=types.PrebuiltVoiceConfig(
                                voice_name="Aoede"
                            )
                        )
                    ),
                ),
            )
            audio_bytes = response.candidates[0].content.parts[0].inline_data.data
            if not audio_bytes or len(audio_bytes) < 512:
                logging.warning("Gemini TTS returned empty audio")
                return False
            with wave.open(str(output_path), "wb") as wav:
                wav.setnchannels(1)
                wav.setsampwidth(2)   # 16-bit
                wav.setframerate(24000)  # Gemini outputs 24kHz PCM
                wav.writeframes(audio_bytes)
            return output_path.exists() and output_path.stat().st_size > 1000
        except Exception as exc:
            logging.warning("Gemini TTS failed: %s", exc)
            return False

    def generate_morning_briefing(
        self,
        memories: dict[str, str],
        events: list[str],
        reminders: list[str],
        weekday: str,
        weather: str = "",
    ) -> str:
        if not self._client:
            return ""

        events_text = "\n".join(f"  - {e}" for e in events) if events else "  Sem eventos marcados."
        reminders_text = (
            "\n".join(f"  - {r}" for r in reminders) if reminders else "  Nenhum lembrete pendente."
        )
        weather_line = f"\nPrevisão do tempo: {weather}" if weather else ""
        bible_version = memories.get("bible_version", "NVI")

        prompt = (
            f"Crie um resumo matinal breve e natural para o Gustavo.\n"
            f"Dia da semana: {weekday}{weather_line}\n\n"
            f"Eventos de hoje:\n{events_text}\n\n"
            f"Lembretes pendentes:\n{reminders_text}\n\n"
            f"Inclua obrigatoriamente:\n"
            f"1. Um versículo bíblico relevante para o dia (versão {bible_version}), com referência mas SEM mencionar o nome da versão\n"
            f"2. A previsão do tempo de forma natural e direta\n\n"
            "Formato: máximo 6 linhas no total, tom natural como um parceiro de confiança falando pessoalmente. "
            "Não use markdown, não use asteriscos. Comece com o versículo."
        )

        try:
            response = self._client.models.generate_content(
                model=self.MODEL,
                contents=prompt,
                config=self._config(memories, max_output_tokens=200, temperature=0.85),
            )
            return response.text.strip()
        except Exception as exc:
            logging.warning("Gemini morning briefing failed: %s", exc)
            return ""
