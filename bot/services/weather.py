from __future__ import annotations

import logging


def fetch_weather(city: str = "São Paulo") -> dict:
    """Fetch today's weather from wttr.in — no API key required."""
    try:
        import httpx
        url = f"https://wttr.in/{city}?format=j1"
        with httpx.Client(timeout=10) as client:
            resp = client.get(url)
            resp.raise_for_status()
            data = resp.json()
        current = data["current_condition"][0]
        today = data["weather"][0]
        desc_raw = current["weatherDesc"][0]["value"]
        desc = _translate(desc_raw)
        return {
            "city": city,
            "temp_c": current["temp_C"],
            "feels_like": current["FeelsLikeC"],
            "description": desc,
            "max_c": today["maxtempC"],
            "min_c": today["mintempC"],
        }
    except Exception as exc:
        logging.warning("Weather fetch failed: %s", exc)
        return {}


def format_weather(w: dict) -> str:
    if not w:
        return ""
    return (
        f"Tempo em {w['city']}: {w['description']}, {w['temp_c']}°C agora "
        f"(sensação {w['feels_like']}°C) — máx {w['max_c']}°C / mín {w['min_c']}°C"
    )


_TRANSLATIONS: dict[str, str] = {
    "Sunny": "Ensolarado",
    "Clear": "Céu limpo",
    "Partly cloudy": "Parcialmente nublado",
    "Cloudy": "Nublado",
    "Overcast": "Encoberto",
    "Mist": "Névoa",
    "Fog": "Neblina",
    "Light rain": "Chuva fraca",
    "Moderate rain": "Chuva moderada",
    "Heavy rain": "Chuva forte",
    "Patchy rain possible": "Possibilidade de chuva",
    "Thundery outbreaks possible": "Possibilidade de trovoadas",
    "Blizzard": "Nevasca",
    "Light snow": "Nevada fraca",
    "Moderate snow": "Nevada moderada",
    "Heavy snow": "Nevada forte",
    "Light drizzle": "Garoa",
    "Freezing drizzle": "Garoa com geada",
    "Light sleet": "Granizo fraco",
    "Moderate or heavy sleet": "Granizo moderado",
    "Thunderstorm": "Tempestade",
}


def _translate(desc: str) -> str:
    return _TRANSLATIONS.get(desc, desc)
