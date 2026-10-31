"""Эмодзи бота.

Каждое эмодзи имеет имя, обычный символ (запасной вариант) и необязательный id премиум-эмодзи.
ID хранятся в data/emoji_map.json и меняются командой /setemoji прямо из бота (только админ).
Если id не задан или Telegram отказался показывать премиум-эмодзи, бот сам
подставляет обычный символ, так что сообщения не ломаются.
"""
import json
import re

import config

FALLBACK = {
    "search": "🔎", "ok": "✅", "bad": "❌", "bolt": "⚡", "crown": "👑", "chart": "📈",
    "hourglass": "⌛️", "target": "🎯", "star": "⭐", "gem": "💎", "copy": "📋",
    "next": "➡️", "home": "🏠", "user": "👤", "bell": "🔔", "trash": "🗑",
    "plus": "➕", "back": "⬅️", "lock": "🔒", "fire": "🔥", "clock": "⏱",
    "info": "ℹ️", "party": "🎉", "money": "💰", "link": "🔗", "stop": "⛔",
    "play": "▶️", "gift": "🎁",
}

_PATH = config.DATA_DIR / "emoji_map.json"
_ids: dict[str, str] = {}


def load() -> None:
    global _ids
    try:
        _ids = json.loads(_PATH.read_text(encoding="utf-8"))
    except Exception:
        _ids = {}


def set_id(name: str, emoji_id: str) -> None:
    if emoji_id in ("", "-", "none"):
        _ids.pop(name, None)
    else:
        _ids[name] = emoji_id
    _PATH.write_text(json.dumps(_ids, ensure_ascii=False, indent=2), encoding="utf-8")


def e(name: str) -> str:
    sym = FALLBACK.get(name, "•")
    eid = _ids.get(name)
    if config.USE_CUSTOM_EMOJI and eid:
        return f'<tg-emoji emoji-id="{eid}">{sym}</tg-emoji>'
    return sym


def plain(name: str) -> str:
    return FALLBACK.get(name, "•")


_TG_EMOJI_RE = re.compile(r'<tg-emoji emoji-id="\d+">(.*?)</tg-emoji>', re.S)


def strip_custom(text: str) -> str:
    """Заменяет <tg-emoji> на обычные символы (запасной вариант при ошибке отправки)."""
    return _TG_EMOJI_RE.sub(r"\1", text)


load()


# ---------------- автоподгрузка из наборов премиум-эмодзи ----------------
_PACKS = config.DATA_DIR / "emoji_packs.json"


def _norm(ch: str) -> str:
    return ch.replace("\ufe0f", "").replace("\u200d", "")


def packs() -> list[str]:
    try:
        saved = json.loads(_PACKS.read_text(encoding="utf-8"))
    except Exception:
        saved = []
    return list(dict.fromkeys(config.EMOJI_PACKS + saved))


def pack_name(link_or_name: str) -> str:
    return link_or_name.strip().rstrip("/").split("/")[-1]


async def load_packs(bot, extra: str | None = None) -> tuple[int, list[str]]:
    """Подбирает премиум-эмодзи по обычным символам из наборов. Возвращает (сколько назначено, чего не нашлось)."""
    if extra:
        names = packs()
        name = pack_name(extra)
        if name not in names:
            names.append(name)
        _PACKS.write_text(json.dumps([n for n in names if n not in config.EMOJI_PACKS]), encoding="utf-8")
    by_char: dict[str, str] = {}
    for name in packs():
        try:
            st = await bot.get_sticker_set(name)
        except Exception:
            continue
        for sticker in st.stickers:
            if sticker.custom_emoji_id and sticker.emoji:
                by_char.setdefault(_norm(sticker.emoji), sticker.custom_emoji_id)
    done, missing = 0, []
    for key, sym in FALLBACK.items():
        eid = by_char.get(_norm(sym))
        if eid:
            _ids[key] = eid
            done += 1
        else:
            missing.append(key)
    if by_char:
        _PATH.write_text(json.dumps(_ids, ensure_ascii=False, indent=2), encoding="utf-8")
    return done, missing
