from __future__ import annotations

import logging
import threading
from pathlib import Path


class LocalWhisperTranscriber:
    def __init__(self) -> None:
        self._model = None
        self._lock = threading.Lock()

    def _load_model(self):
        with self._lock:
            if self._model is None:
                from faster_whisper import WhisperModel
                logging.info("Loading local Whisper model (tiny/cpu/int8)")
                self._model = WhisperModel("tiny", device="cpu", compute_type="int8")
        return self._model

    def preload(self) -> None:
        """Eagerly loads the model so the first audio message has no cold-start delay."""
        try:
            self._load_model()
            logging.info("Local Whisper model pre-loaded successfully")
        except Exception as exc:
            logging.warning("Could not pre-load Whisper model: %s", exc)

    def transcribe(self, audio_path: Path) -> str:
        model = self._load_model()
        segments, _info = model.transcribe(
            str(audio_path),
            language="pt",
            beam_size=1,
            vad_filter=True,
        )
        return " ".join(segment.text.strip() for segment in segments).strip()


async def synthesize_with_edge_tts(text: str, output_path: Path) -> bool:
    try:
        import edge_tts
        communicate = edge_tts.Communicate(
            text[:3500],
            voice="pt-BR-ThalitaMultilingualNeural",
            rate="+0%",
        )
        await communicate.save(str(output_path))
        return output_path.exists() and output_path.stat().st_size > 0
    except Exception as exc:
        logging.warning("Edge TTS failed: %s", type(exc).__name__)
        return False
