from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Intent:
    name: str
    data: dict[str, str]


# Verbos de ação que indicam CRIAÇÃO (têm prioridade sobre listas)
CREATE_EVENT_TRIGGERS = (
    "agendar", "agende", "marca", "marcar", "marque",
    "cadastre", "cadastrar", "adicione", "anote",
    "reserva", "reservar", "insira",
)
# Tipos de evento — ficam no título, não são removidos
EVENT_TYPE_WORDS = ("reuniao", "reunião", "compromisso", "evento", "encontro", "consulta")
EVENT_WORDS = CREATE_EVENT_TRIGGERS + EVENT_TYPE_WORDS

REMINDER_WORDS = (
    "me lembra de",
    "me lembre de",
    "lembra de",
    "lembrar de",
    "lembrete",
    "me avisa",
    "avisa",
    "avisar",
    "lembra",
    "lembrar",
)
STUDY_WORDS = ("estudar", "estudo", "aprender", "revisar", "preciso ver", "preciso entender")
LIST_STUDY_WORDS = ("meus estudos", "o que tenho que estudar", "lista estudos", "ver estudos")
LIST_EVENT_WORDS = ("minha agenda", "meus eventos", "proximos eventos", "ver agenda", "ver eventos", "quais eventos")
LIST_REMINDER_WORDS = ("meus lembretes", "ver lembretes", "quais lembretes")
ROUTINE_WORDS = ("minha rotina", "rotina", "meus horarios", "horarios")
WEEK_PLANNING_WORDS = ("organizar semana", "planejar semana", "minha semana", "semana")
PROJECT_WORDS = ("projeto", "projetos", "desenvolver", "programar", "meu pc")
GREETING_WORDS = (
    "oi", "olá", "ola", "e ai", "e aí", "bom dia", "boa tarde", "boa noite",
    "tudo bem", "tudo bom", "como vai", "hey", "hi", "salve", "fala", "opa",
)
AUDIO_REQUEST_WORDS = (
    "manda um audio", "manda audio", "me manda um audio", "me manda audio",
    "fala sobre", "explica falando", "me explica em audio", "fala pra mim",
    "responde em audio", "responda em audio", "me fala sobre", "conta falando",
)
SEARCH_WORDS = (
    "pesquisa", "pesquise", "pesquisar", "busca ", "busque", "buscar",
    "notícias", "noticias", "noticia", "notícia",
    "o que aconteceu", "o que está acontecendo", "o que esta acontecendo",
    "qual o preço", "qual é o preço", "qual valor", "qual o valor",
    "cotação", "cotacao", "cotação do", "cotação da",
    "quanto está o", "quanto esta o", "quanto custa",
    "valor do dólar", "valor do dollar", "valor do euro", "valor do real",
    "me fala das notícias", "me fala das noticias",
    "últimas notícias", "ultimas noticias",
    "hoje no mundo", "o que há de novo", "o que ha de novo",
    "previsão do tempo", "previsao do tempo",
)
CLOTHESLINE_WORDS = (
    "estender roupa", "estender roupas", "posso estender", "pode estender",
    "roupa no varal", "roupas no varal", "varal", "secar roupa", "secar roupas",
    "pendurar roupa",
)
VIEW_CAMERA_WORDS = (
    "câmera", "camera", "cam ", "canal ", "mostre a câmera", "ver câmera",
    "mostra câmera", "o que tem na câmera", "o que está na câmera",
)
SURVEILLANCE_WORDS = (
    "ligar vigilância", "desligar vigilância", "ativar câmera", "desativar câmera",
    "ligar monitoramento", "desligar monitoramento", "vigilância ligada",
)


def detect_intent(text: str) -> Intent:
    lowered = normalize(text)

    # Creation verbs override everything — check BEFORE list detection
    if contains_any(lowered, CREATE_EVENT_TRIGGERS):
        if contains_any(lowered, STUDY_WORDS):
            return Intent("create_study", {"topic": extract_study_topic(text)})
        if contains_any(lowered, REMINDER_WORDS):
            title, when_text = split_title_and_time(text, REMINDER_WORDS)
            return Intent("create_reminder", {"title": title, "when_text": when_text})
        title, when_text = split_title_and_time(text, CREATE_EVENT_TRIGGERS)
        # Only use fallback when truly empty — "Compromisso" is already a valid placeholder
        if not title:
            title = _extract_event_title(text)
        return Intent("create_event", {"title": title, "when_text": when_text})

    if contains_any(lowered, LIST_STUDY_WORDS):
        return Intent("list_studies", {})
    if contains_any(lowered, LIST_EVENT_WORDS):
        return Intent("list_events", {})
    if contains_any(lowered, LIST_REMINDER_WORDS):
        return Intent("list_reminders", {})
    if contains_any(lowered, ROUTINE_WORDS):
        return Intent("routine", {})
    if contains_any(lowered, WEEK_PLANNING_WORDS):
        return Intent("plan_week", {})
    if contains_any(lowered, PROJECT_WORDS):
        return Intent("project_chat", {})
    if contains_any(lowered, REMINDER_WORDS):
        title, when_text = split_title_and_time(text, REMINDER_WORDS)
        return Intent("create_reminder", {"title": title, "when_text": when_text})
    if contains_any(lowered, STUDY_WORDS):
        return Intent("create_study", {"topic": extract_study_topic(text)})
    if contains_any(lowered, EVENT_TYPE_WORDS) or has_time_expression(lowered):
        title, when_text = split_title_and_time(text, CREATE_EVENT_TRIGGERS)
        if not title:
            title = _extract_event_title(text)
        return Intent("create_event", {"title": title, "when_text": when_text})
    # Web search
    if contains_any(lowered, SEARCH_WORDS):
        return Intent("web_search", {"query": text.strip()})

    # Camera / surveillance intents
    if contains_any(lowered, CLOTHESLINE_WORDS):
        return Intent("check_clothesline", {})
    if contains_any(lowered, VIEW_CAMERA_WORDS):
        channel = _extract_channel_number(lowered)
        return Intent("view_camera", {"channel": channel})
    if contains_any(lowered, SURVEILLANCE_WORDS):
        on = any(w in lowered for w in ("ligar", "ativar"))
        return Intent("toggle_surveillance", {"on": "true" if on else "false"})

    # Greet only when message is short and clearly a greeting
    if contains_any(lowered, GREETING_WORDS) and len(lowered.split()) <= 5:
        return Intent("greeting", {})
    return Intent("chat", {})


def local_chat_reply(text: str) -> str:
    lowered = normalize(text)
    if contains_any(lowered, WEEK_PLANNING_WORDS):
        return (
            "Vamos organizar sua semana. Me fale como vai ser cada dia — "
            "compromissos, estudos, projetos. Eu separo tudo."
        )
    if contains_any(lowered, PROJECT_WORDS):
        return (
            "Me diz o nome do projeto e o que você quer fazer nele agora: "
            "corrigir algo, criar uma função, planejar ou estudar o código?"
        )
    if "igreja" in lowered:
        return "Igreja já está na sua rotina. Quer marcar algo específico?"
    if "email" in lowered or "gmail" in lowered:
        return (
            "A integração com Gmail ainda precisa de configuração OAuth. "
            "Quando estiver pronto, consigo resumir emails e criar eventos automaticamente."
        )
    return (
        "Pode me dizer o que precisa: estudo, compromisso, lembrete ou projeto. "
        "Fala naturalmente que eu organizo."
    )


def _extract_event_title(text: str) -> str:
    """Tries to extract a meaningful event title from the raw text."""
    skip = {
        # action verbs
        "cadastre", "cadastrar", "adicione", "insira", "anote", "agendar", "agende",
        "marca", "marcar", "marque", "reserva", "reservar",
        # articles / prepositions that are not part of the title
        "uma", "um", "o", "a", "de", "da", "do", "para", "pra",
    }
    words = [w for w in text.split() if w.lower() not in skip]
    # Remove trailing time expressions
    cleaned = re.sub(
        r"\b(?:hoje|amanha|amanhã|segunda|terca|terça|quarta|quinta|sexta|sabado|sábado|domingo)"
        r"[\s,]*(?:as|às|a)?\s*\d{1,2}(?::\d{2}|h\d{0,2})?\b.*",
        "",
        " ".join(words),
        flags=re.I,
    ).strip(" ,.-")
    return cleaned or "Compromisso"


def _extract_channel_number(text: str) -> str:
    """Extract camera channel number from text like 'câmera 3' or 'canal 7'."""
    match = re.search(r"\b(\d+)\b", text)
    return match.group(1) if match else ""


def normalize(text: str) -> str:
    return text.strip().lower()


def contains_any(text: str, words: tuple[str, ...]) -> bool:
    return any(word in text for word in words)


def has_time_expression(text: str) -> bool:
    return bool(re.search(r"\b(\d{1,2})(h|:\d{2})\b", text))


def extract_study_topic(text: str) -> str:
    patterns = [
        r".*?(?:preciso|quero|devo)?\s*(?:estudar|aprender|revisar|entender)\s+(.*)",
        r".*?preciso ver\s+(.*)",
    ]
    for pattern in patterns:
        match = re.match(pattern, text.strip(), flags=re.I)
        if match and match.group(1).strip():
            return match.group(1).strip(" .")
    return text.strip()


_TITLE_NOISE = re.compile(
    r"\b(minha agenda|meu lembrete|no meu calendário|no calendário|minha lista)\b",
    flags=re.I,
)
_LEADING_ARTICLE = re.compile(r"^\s*(?:uma?|o|a)\s+", flags=re.I)
_TIME_RE = re.compile(
    r"\b(hoje|amanha|amanhã|segunda|terca|terça|quarta|quinta|sexta|sabado|sábado|domingo)?"
    r"[\s,]*(?:as|às|a)?\s*(\d{1,2}(?::\d{2}|h\d{0,2})?)[\s,]*(?:horas?)?\b",
    flags=re.I,
)
_DATE_RE = re.compile(
    r"\b(hoje|amanha|amanhã|segunda|terca|terça|quarta|quinta|sexta|sabado|sábado|domingo)\b.*",
    flags=re.I,
)


def _clean_title(raw: str) -> str:
    result = _TITLE_NOISE.sub("", raw)
    result = _LEADING_ARTICLE.sub("", result)
    return result.strip(" ,.-") or "Compromisso"


def split_title_and_time(text: str, trigger_words: tuple[str, ...]) -> tuple[str, str]:
    cleaned = text.strip()
    cleaned_without_trigger = re.sub(
        "|".join(re.escape(word) for word in trigger_words),
        " ",
        cleaned,
        flags=re.I,
    ).strip(" .")

    time_match = _TIME_RE.search(cleaned_without_trigger)
    if time_match:
        when_text = time_match.group(0).strip()
        title = _clean_title(cleaned_without_trigger.replace(time_match.group(0), ""))
        return title, when_text

    date_match = _DATE_RE.search(cleaned_without_trigger)
    if date_match:
        when_text = date_match.group(0).strip()
        title = _clean_title(cleaned_without_trigger.replace(date_match.group(0), ""))
        return title, when_text

    return _clean_title(cleaned_without_trigger), "sem horário definido"
