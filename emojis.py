"""
Эмодзи бота.

Каждое эмодзи имеет:
- symbol — обычный символ (запасной вариант).
- id — ID Telegram Premium Emoji.

ID можно задавать прямо в FALLBACK или через /setemoji.
Приоритет имеет ID из emoji_map.json.

Также поддерживается автоматическая загрузка эмодзи из наборов.
"""

import json
import re

import config


# ============================================================
# ЭМОДЗИ И ИХ ID
# Вставляй ID Premium Emoji в поле "id".
# Если ID нет — оставляй пустую строку.
# ============================================================

FALLBACK = {
    "search": {"symbol": "🔎", "id": "5258396243666681152"},
    "ok": {"symbol": "✅", "id": "5825794181183836432"},
    "bad": {"symbol": "❌", "id": "5807692706507399432"},
    "bolt": {"symbol": "⚡", "id": "5172425562634847208"},
    "crown": {"symbol": "👑", "id": "5807868868886009920"},
    "chart": {"symbol": "📈", "id": "5994378914636500516"},
    "hourglass": {"symbol": "⌛️", "id": "5258419835922030550"},
    "target": {"symbol": "🎯", "id": "5935989710420709120"},
    "star": {"symbol": "⭐", "id": "5310224206732996002"},
    "gem": {"symbol": "💎", "id": "5807465992363710697"},
    "copy": {"symbol": "📋", "id": "6021435576513730578"},
    "next": {"symbol": "➡️", "id": "5875506366050734240"},
    "home": {"symbol": "🏠", "id": "5257963315258204021"},
    "user": {"symbol": "👤", "id": "5879770735999717115"},
    "bell": {"symbol": "🔔", "id": "5909201569898827582"},
    "trash": {"symbol": "🗑", "id": "5258130763148172425"},
    "plus": {"symbol": "➕", "id": "5274008024585871702"},
    "back": {"symbol": "⬅️", "id": "5877536313623711363"},
    "lock": {"symbol": "🔒", "id": "5879895758202735862"},
    "fire": {"symbol": "🔥", "id": "6008104758236156926"},
    "clock": {"symbol": "⏱", "id": ""},
    "info": {"symbol": "ℹ️", "id": "5258043150110301407"},
    "party": {"symbol": "🎉", "id": "6023579259115674297"},
    "money": {"symbol": "💰", "id": "5967390100357648692"},
    "link": {"symbol": "🔗", "id": "5260730055880876557"},
    "stop": {"symbol": "⛔", "id": "5017122105011995219"},
    "play": {"symbol": "▶️", "id": "5255835489675519149"},
    "gift": {"symbol": "🎁", "id": "5875180111744995604"},
}


# ============================================================
# ФАЙЛЫ
# ============================================================

_PATH = config.DATA_DIR / "emoji_map.json"
_PACKS = config.DATA_DIR / "emoji_packs.json"

_ids: dict[str, str] = {}


# ============================================================
# ЗАГРУЗКА ID
# ============================================================

def load() -> None:
    global _ids

    try:
        data = json.loads(_PATH.read_text(encoding="utf-8"))

        if isinstance(data, dict):
            _ids = {
                str(key): str(value)
                for key, value in data.items()
                if key in FALLBACK and value
            }
        else:
            _ids = {}

    except (FileNotFoundError, json.JSONDecodeError, OSError):
        _ids = {}


# ============================================================
# СОХРАНЕНИЕ ID
# ============================================================

def _save() -> None:
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)

    _PATH.write_text(
        json.dumps(_ids, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )


def set_id(name: str, emoji_id: str) -> None:
    name = name.lower().strip()
    emoji_id = emoji_id.strip()

    if name not in FALLBACK:
        raise ValueError(f"Неизвестное эмодзи: {name}")

    if emoji_id.lower() in ("", "-", "none"):
        _ids.pop(name, None)
    else:
        if not emoji_id.isdigit():
            raise ValueError("ID должен содержать только цифры.")

        _ids[name] = emoji_id

    _save()


# ============================================================
# ПОЛУЧЕНИЕ ЭМОДЗИ
# ============================================================

def e(name: str) -> str:
    item = FALLBACK.get(name)

    if not item:
        return "•"

    symbol = item["symbol"]

    # Сначала ID из JSON, затем ID непосредственно из кода.
    emoji_id = _ids.get(name) or item["id"]

    if config.USE_CUSTOM_EMOJI and emoji_id:
        return f'<tg-emoji emoji-id="{emoji_id}">{symbol}</tg-emoji>'

    return symbol


def plain(name: str) -> str:
    item = FALLBACK.get(name)

    if not item:
        return "•"

    return item["symbol"]


# ============================================================
# УДАЛЕНИЕ PREMIUM EMOJI
# ============================================================

_TG_EMOJI_RE = re.compile(
    r'<tg-emoji\s+emoji-id="\d+">(.*?)</tg-emoji>',
    re.S
)


def strip_custom(text: str) -> str:
    """Заменяет Premium Emoji обычными символами."""

    return _TG_EMOJI_RE.sub(r"\1", text)


# Загружаем ID при импорте модуля.
load()


# ============================================================
# РАБОТА С НАБОРАМИ PREMIUM EMOJI
# ============================================================

def _norm(ch: str) -> str:
    return (
        ch.replace("\ufe0f", "")
          .replace("\u200d", "")
    )


def packs() -> list[str]:
    try:
        saved = json.loads(
            _PACKS.read_text(encoding="utf-8")
        )

        if not isinstance(saved, list):
            saved = []

    except (FileNotFoundError, json.JSONDecodeError, OSError):
        saved = []

    return list(
        dict.fromkeys(config.EMOJI_PACKS + saved)
    )


def pack_name(link_or_name: str) -> str:
    return link_or_name.strip().rstrip("/").split("/")[-1]


async def load_packs(bot, extra: str | None = None) -> tuple[int, list[str]]:
    """
    Загружает Premium Emoji из наборов Telegram.

    Возвращает:
    (количество найденных эмодзи, список ненайденных названий).
    """

    if extra:
        names = packs()
        name = pack_name(extra)

        if name not in names:
            names.append(name)

        config.DATA_DIR.mkdir(parents=True, exist_ok=True)

        _PACKS.write_text(
            json.dumps(
                [n for n in names if n not in config.EMOJI_PACKS],
                ensure_ascii=False,
                indent=2
            ),
            encoding="utf-8"
        )

    by_char: dict[str, str] = {}

    for name in packs():
        try:
            sticker_set = await bot.get_sticker_set(name)

        except Exception:
            continue

        for sticker in sticker_set.stickers:
            if sticker.custom_emoji_id and sticker.emoji:
                by_char.setdefault(
                    _norm(sticker.emoji),
                    sticker.custom_emoji_id
                )

    done = 0
    missing = []

    for key, item in FALLBACK.items():
        emoji_id = by_char.get(
            _norm(item["symbol"])
        )

        # Не перезаписываем ID, указанные вручную в коде.
        if item["id"]:
            continue

        if emoji_id:
            _ids[key] = emoji_id
            done += 1
        else:
            missing.append(key)

    if done:
        _save()

    return done, missing
