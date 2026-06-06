from __future__ import annotations

import logging
import re
import subprocess
import threading
from dataclasses import dataclass
from pathlib import Path

from google import genai
from google.genai import types


@dataclass
class CameraConfig:
    channel: int
    name: str
    description: str
    monitor: bool = True
    high_priority: bool = False  # alert immediately even at night


# Configuração dos canais
CAMERAS: dict[int, CameraConfig] = {
    3: CameraConfig(3, "Portão Grande", "entrada de veículos e portão grande", monitor=True, high_priority=True),
    5: CameraConfig(5, "Varal (câm. 5)", "área do varal onde se estende roupas", monitor=True),
    7: CameraConfig(7, "Entrada da Casa", "entrada principal da casa e portão de pedestres", monitor=True, high_priority=True),
    8: CameraConfig(8, "Varal (câm. 8)", "área do varal onde se estende roupas", monitor=True),
    # Canal 6 (cozinha) não monitorado
}

CLOTHESLINE_CHANNELS = [5, 8]
ENTRANCE_CHANNELS = [3, 7]
MONITORED_CHANNELS = [c.channel for c in CAMERAS.values() if c.monitor]

_capture_lock = threading.Lock()


def _rtsp_url(base_url: str, channel: int, sub: int = 1) -> str:
    """Build RTSP URL for a specific channel. sub=1 for lower-res sub-stream."""
    url = re.sub(r"channel=\d+", f"channel={channel}", base_url)
    url = re.sub(r"subtype=\d+", f"subtype={sub}", url)
    return url


def _capture_opencv(rtsp_url: str) -> bytes | None:
    try:
        import cv2
        cap = cv2.VideoCapture(rtsp_url, cv2.CAP_FFMPEG)
        cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 8000)
        cap.set(cv2.CAP_PROP_READ_TIMEOUT_MSEC, 8000)
        # Skip first few frames to get a stable image
        for _ in range(3):
            cap.grab()
        ret, frame = cap.read()
        cap.release()
        if ret and frame is not None:
            _, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
            return bytes(buf)
        return None
    except Exception as exc:
        logging.debug("OpenCV capture failed ch%s: %s", rtsp_url[-20:], exc)
        return None


def _capture_ffmpeg(rtsp_url: str) -> bytes | None:
    try:
        cmd = [
            "ffmpeg", "-y",
            "-rtsp_transport", "tcp",
            "-stimeout", "8000000",
            "-i", rtsp_url,
            "-vframes", "1",
            "-f", "image2",
            "-vcodec", "mjpeg",
            "-loglevel", "quiet",
            "pipe:1",
        ]
        result = subprocess.run(cmd, capture_output=True, timeout=15)
        if result.returncode == 0 and len(result.stdout) > 1000:
            return result.stdout
        return None
    except Exception as exc:
        logging.debug("FFmpeg capture failed: %s", exc)
        return None


def capture_frame(base_url: str, channel: int, high_quality: bool = False) -> bytes | None:
    """Capture a JPEG frame from the given channel. Thread-safe."""
    sub = 0 if high_quality else 1
    url = _rtsp_url(base_url, channel, sub)
    with _capture_lock:
        frame = _capture_opencv(url)
        if frame:
            return frame
        return _capture_ffmpeg(url)


def analyze_frame(client: genai.Client, image_bytes: bytes, prompt: str) -> str:
    """Send a JPEG frame to Gemini Vision and get a description."""
    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[
                types.Content(
                    role="user",
                    parts=[
                        types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg"),
                        types.Part.from_text(text=prompt),
                    ],
                )
            ],
            config=types.GenerateContentConfig(max_output_tokens=300, temperature=0.2),
        )
        return response.text.strip()
    except Exception as exc:
        logging.warning("Gemini Vision failed: %s", exc)
        return ""


def check_clothesline(client: genai.Client, base_url: str) -> tuple[str, list[bytes]]:
    """
    Capture channels 5 and 8, analyze if it's safe to hang clothes.
    Returns (text_response, list_of_images).
    """
    images: list[bytes] = []
    descriptions: list[str] = []

    for ch in CLOTHESLINE_CHANNELS:
        frame = capture_frame(base_url, ch, high_quality=True)
        if not frame:
            descriptions.append(f"Câmera {ch}: sem sinal")
            continue
        images.append(frame)
        desc = analyze_frame(
            client,
            frame,
            "Esta é uma câmera de segurança do varal de uma casa.\n"
            "Responda em 2 frases curtas:\n"
            "1. Tem roupas penduradas no varal? (sim ou não)\n"
            "2. O clima/luz visível sugere chuva ou sol?",
        )
        cam_name = CAMERAS[ch].name
        descriptions.append(f"{cam_name}: {desc}" if desc else f"{cam_name}: sem análise")

    combined = "\n".join(descriptions)
    if not images:
        return "Não consegui acessar as câmeras do varal agora.", images

    # Final verdict — direct answer only
    verdict = analyze_frame(
        client,
        images[0],
        f"Observações do varal:\n{combined}\n\n"
        "Responda APENAS com uma dessas frases e depois explique em UMA frase o motivo:\n"
        "- 'Pode estender roupa.' (se o varal tiver espaço e não estiver chovendo)\n"
        "- 'Não pode estender roupa.' (se tiver chuva ou o varal estiver lotado)\n"
        "- 'Varal parcialmente livre.' (se tiver espaço mas já tiver alguma roupa)\n"
        "Seja direto, máximo 2 frases.",
    )
    return verdict or combined, images


def check_suspicious(
    client: genai.Client,
    base_url: str,
    channels: list[int] | None = None,
) -> list[tuple[int, str, bytes]]:
    """
    Analyze specified (or all monitored) channels for suspicious activity.
    Returns list of (channel, description, image_bytes) only for channels with activity.
    """
    targets = channels or MONITORED_CHANNELS
    alerts: list[tuple[int, str, bytes]] = []

    for ch in targets:
        frame = capture_frame(base_url, ch)
        if not frame:
            continue
        cam = CAMERAS.get(ch)
        cam_desc = cam.description if cam else f"câmera {ch}"
        analysis = analyze_frame(
            client,
            frame,
            f"Esta é a {cam_desc} de uma residência.\n"
            "Responda APENAS se houver pessoa, veículo ou animal visível:\n"
            "- Se houver: descreva em 1 frase o que vê (quem/o quê, onde, o que está fazendo).\n"
            "- Se não houver: responda exatamente 'vazio'.",
        )
        if analysis and analysis.lower().strip() not in ("vazio", "", "sem atividade"):
            alerts.append((ch, analysis, frame))

    return alerts


def view_channel(client: genai.Client, base_url: str, channel: int) -> tuple[str, bytes | None]:
    """Capture and describe what's currently on a specific channel."""
    cam = CAMERAS.get(channel)
    if not cam:
        return f"Canal {channel} não está configurado.", None

    frame = capture_frame(base_url, channel, high_quality=True)
    if not frame:
        return f"Não consegui acessar a câmera {cam.name} agora.", None

    description = analyze_frame(
        client,
        frame,
        f"Descreva em 2-3 frases o que está acontecendo nesta câmera ({cam.description}). "
        "Seja específico sobre pessoas, veículos, condições climáticas visíveis e qualquer movimento.",
    )
    return description or f"Câmera {cam.name} online.", frame
