from __future__ import annotations

import logging
import re

# ---------------------------------------------------------------------------
# Currency / financial data
# ---------------------------------------------------------------------------

_CURRENCY_MAP = {
    "dólar": "USD-BRL",
    "dollar": "USD-BRL",
    "dolar": "USD-BRL",
    "usd": "USD-BRL",
    "euro": "EUR-BRL",
    "eur": "EUR-BRL",
    "libra": "GBP-BRL",
    "gbp": "GBP-BRL",
    "bitcoin": "BTC-BRL",
    "btc": "BTC-BRL",
    "ethereum": "ETH-BRL",
    "eth": "ETH-BRL",
}


def fetch_currency(query: str) -> str:
    """Fetch real-time currency rate from awesomeapi.com.br (no API key required)."""
    lowered = query.lower()
    pair = next((code for kw, code in _CURRENCY_MAP.items() if kw in lowered), None)
    if not pair:
        return ""
    try:
        import httpx
        url = f"https://economia.awesomeapi.com.br/json/last/{pair}"
        with httpx.Client(timeout=8) as client:
            data = client.get(url).json()
        info = data[pair.replace("-", "")]
        bid = float(info["bid"])
        high = float(info["high"])
        low = float(info["low"])
        pct = float(info["pctChange"])
        name = info["name"]
        sign = "+" if pct >= 0 else ""
        return (
            f"{name}: R$ {bid:.4f} | Máx hoje: R$ {high:.4f} | "
            f"Mín hoje: R$ {low:.4f} | Variação: {sign}{pct:.2f}%"
        )
    except Exception as exc:
        logging.warning("Currency fetch failed (%s): %s", pair, exc)
        return ""


# Prefixes to strip before sending to DuckDuckGo
_STRIP = re.compile(
    r"^("
    r"pesquise?\s*(na\s+internet)?\s*(para\s+mim)?\s*[,:]?\s*"
    r"|busque?\s*(na\s+internet)?\s*(para\s+mim)?\s*[,:]?\s*"
    r"|me\s+fala\s+d[ae]s?\s+not[ií]cias\s*(de|sobre)?\s*"
    r"|not[ií]cias\s*(de|sobre)?\s*"
    r"|qual\s+(é\s+|e\s+)?o?\s*valor\s+d[eo]\s*"
    r"|qual\s+a\s+cota[çc][aã]o\s+d[eo]?\s*"
    r"|quanto\s+est[aá]\s+o?\s*"
    r"|quanto\s+custa\s*"
    r")",
    flags=re.I,
)


def clean_query(raw: str) -> str:
    """Strip search trigger phrases, return a clean query for DuckDuckGo."""
    q = _STRIP.sub("", raw.strip()).strip(" ,?")
    return q or raw.strip()


def web_search(query: str, max_results: int = 5) -> list[dict]:
    """Search the web using DuckDuckGo. No API key required."""
    q = clean_query(query)
    logging.info("Web search query: %r", q)
    try:
        from duckduckgo_search import DDGS
        results = list(DDGS().text(q, max_results=max_results, region="br-pt"))
        logging.info("Web search returned %d results", len(results))
        return [
            {
                "title": r.get("title", ""),
                "url": r.get("href", ""),
                "snippet": r.get("body", ""),
            }
            for r in results
        ]
    except Exception as exc:
        logging.warning("Web search failed: %s", exc)
        return []


def format_for_ai(query: str, results: list[dict]) -> str:
    if not results:
        return f"Nenhum resultado encontrado para: {query}"
    lines = [f"Resultados da web para '{query}':\n"]
    for i, r in enumerate(results, 1):
        lines.append(f"{i}. {r['title']}\n   {r['snippet']}\n   Fonte: {r['url']}")
    return "\n\n".join(lines)
