from __future__ import annotations

import datetime as dt
import logging
from typing import Callable, Awaitable

import pytz

from bot.services.camera import CAMERAS, check_suspicious


class SurveillanceService:
    """
    Manages periodic camera checks and alert cooldowns.
    Prevents spamming the user with repeated alerts for the same channel.
    """

    # Minimum seconds between alerts for the same channel
    COOLDOWN_SECONDS = 600  # 10 minutes

    def __init__(self, timezone: str = "America/Sao_Paulo") -> None:
        self._tz = pytz.timezone(timezone)
        self._last_alert: dict[int, dt.datetime] = {}
        self.enabled = True

    def _can_alert(self, channel: int) -> bool:
        last = self._last_alert.get(channel)
        if last is None:
            return True
        elapsed = (dt.datetime.now(self._tz) - last).total_seconds()
        return elapsed >= self.COOLDOWN_SECONDS

    def _mark_alerted(self, channel: int) -> None:
        self._last_alert[channel] = dt.datetime.now(self._tz)

    async def run_check(
        self,
        client,
        base_url: str,
        send_alert: Callable[[int, str, bytes], Awaitable[None]],
    ) -> None:
        """
        Capture all monitored channels, analyze with Gemini Vision,
        and call send_alert for any new activity (respecting cooldowns).
        """
        if not self.enabled or not base_url:
            return

        try:
            alerts = check_suspicious(client, base_url)
        except Exception as exc:
            logging.warning("Surveillance check failed: %s", exc)
            return

        for channel, description, frame in alerts:
            if not self._can_alert(channel):
                logging.debug("Channel %d in cooldown, skipping alert", channel)
                continue
            cam = CAMERAS.get(channel)
            cam_name = cam.name if cam else f"Câmera {channel}"
            try:
                await send_alert(channel, f"{cam_name}: {description}", frame)
                self._mark_alerted(channel)
            except Exception as exc:
                logging.warning("Failed to send surveillance alert ch%d: %s", channel, exc)

    def reset_cooldown(self, channel: int | None = None) -> None:
        if channel:
            self._last_alert.pop(channel, None)
        else:
            self._last_alert.clear()
