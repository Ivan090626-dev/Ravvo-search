"""Тексты и клавиатуры."""
from datetime import datetime, timezone

from aiogram.types import CopyTextButton, InlineKeyboardButton as B, InlineKeyboardMarkup as KB

import config
from core import fmt_left, remaining
from emojis import e, plain


def kb(rows: list[list[B]]) -> KB:
    return KB(inline_keyboard=rows)


def ts_date(ts: int) -> str:
    return datetime.fromtimestamp(ts, timezone.utc).strftime("%d.%m.%Y")


# ------------------------------- главное меню -------------------------------
async def left_line(uid: int) -> str:
    i5, i6 = await remaining(uid, "i5"), await remaining(uid, "i6")
    return f"{e('hourglass')} Осталось: 5 букв — <b>{fmt_left(i5)}</b>, 6 букв — <b>{fmt_left(i6)}</b>"


async def menu_text(uid: int) -> str:
    return (
        f"{e('search')} <b>Поиск свободных ников</b>\n\n"
        f"{e('ok')} Telegram — свободен от профилей и ботов\n"
        f"{e('ok')} Fragment — не на аукционе\n\n"
        f"{e('bolt')} <b>Моментальный</b> — ник за секунду. Чаще это наборы букв "
        f"(<code>xqzvt</code>), но попадаются и нормальные.\n\n"
        f"{e('crown')} <b>Premium-поиск</b> — доступен всем. Только читаемые ники, без наборов букв. "
        f"Ищет дольше: такие почти все уже разобраны.\n\n"
        f"{e('chart')} <b>Автопоиск</b> — сам ищет ник нужной цены (с подпиской Premium).\n\n"
        + await left_line(uid)
    )


def menu_kb() -> KB:
    return kb([
        [B(text=f"{plain('bolt')} 5 букв", callback_data="s:5:i"),
         B(text=f"{plain('bolt')} 6 букв", callback_data="s:6:i")],
        [B(text=f"{plain('crown')} 5 букв Premium", callback_data="s:5:p"),
         B(text=f"{plain('crown')} 6 букв Premium", callback_data="s:6:p")],
        [B(text=f"{plain('chart')} Автопоиск", callback_data="auto"),
         B(text=f"{plain('target')} Ловушки", callback_data="traps")],
        [B(text=f"{plain('gem')} Premium", callback_data="premium"),
         B(text=f"{plain('user')} Профиль", callback_data="profile")],
    ])


def back_kb() -> KB:
    return kb([[B(text=f"{plain('home')} В меню", callback_data="menu")]])


# --------------------------------- результат --------------------------------
async def found_text(uid: int, name: str, length: int, mode: str) -> str:
    kind = f"{e('bolt')} Моментальный" if mode == "i" else f"{e('crown')} Premium-поиск"
    return (
        f"{e('party')} <b>Нашёл свободный ник</b>\n\n"
        f"{e('user')} <code>@{name}</code>\n\n"
        f"{e('ok')} Telegram — свободен\n"
        f"{e('ok')} Fragment — не на аукционе\n\n"
        f"{kind} · {length} букв\n"
        + await left_line(uid)
    )


def found_kb(name: str, length: int, mode: str) -> KB:
    return kb([
        [B(text=f"{plain('copy')} Скопировать", copy_text=CopyTextButton(text=f"@{name}")),
         B(text=f"{plain('next')} Дальше", callback_data=f"s:{length}:{mode}")],
        [B(text=f"{plain('target')} Проверить на t.me", url=f"https://t.me/{name}"),
         B(text=f"{plain('home')} Меню", callback_data="menu")],
    ])


def searching_text(length: int, mode: str) -> str:
    what = "моментальный поиск" if mode == "i" else "Premium-поиск (читаемые ники, это дольше)"
    return f"{e('search')} <b>Ищу свободный ник из {length} букв…</b>\n{e('clock')} Режим: {what}"


def not_found_kb(length: int, mode: str) -> KB:
    return kb([
        [B(text=f"{plain('next')} Искать ещё", callback_data=f"s:{length}:{mode}")],
        [B(text=f"{plain('home')} Меню", callback_data="menu")],
    ])


def not_found_text(length: int, mode: str) -> str:
    return (
        f"{e('hourglass')} <b>Пока не нашёл</b>\n\n"
        f"Все проверенные ники из {length} букв оказались заняты или Telegram ограничил запросы. "
        f"Нажмите «Искать ещё»."
    )


def limit_text(length: int, mode: str) -> str:
    return (
        f"{e('lock')} <b>Лимит на сегодня исчерпан</b>\n\n"
        f"Для обычных пользователей поиск ограничен. С подпиской Premium лимиты "
        f"намного выше, плюс автопоиск и до {config.TRAP_SLOTS['premium']} ловушек.\n\n"
        f"Лимиты обновляются в 00:00 UTC."
    )


def limit_kb() -> KB:
    return kb([
        [B(text=f"{plain('gem')} Premium — {config.PREMIUM_PRICE_STARS} ⭐/мес", callback_data="premium")],
        [B(text=f"{plain('home')} В меню", callback_data="menu")],
    ])


# --------------------------------- ловушки ----------------------------------
async def traps_text(uid: int, tier_name: str, traps) -> str:
    slots = config.TRAP_SLOTS[tier_name]
    head = (
        f"{e('target')} <b>Ловушки</b>\n\n"
        f"Добавьте занятый ник — как только он освободится, пришлю уведомление. "
        f"Проверяю каждые {config.TRAP_INTERVAL // 60} мин.\n"
    )
    if traps:
        body = "\n" + "\n".join(f"{e('bell')} <code>@{t['username']}</code>" for t in traps) + "\n"
    else:
        body = "\nПока ни одного ника.\n"
    return head + body + f"\nСлотов: <b>{len(traps)}/{slots}</b>"


def traps_kb(traps) -> KB:
    rows = [[B(text=f"{plain('plus')} Добавить ник", callback_data="trap_add")]]
    for t in traps[:40]:
        rows.append([B(text=f"{plain('trash')} @{t['username']}", callback_data=f"trap_del:{t['id']}")])
    if traps:
        rows.append([B(text=f"{plain('stop')} Очистить все", callback_data="trap_clear")])
    rows.append([B(text=f"{plain('home')} В меню", callback_data="menu")])
    return kb(rows)


def trap_hit_kb(name: str) -> KB:
    return kb([
        [B(text=f"{plain('copy')} Скопировать", copy_text=CopyTextButton(text=f"@{name}")),
         B(text=f"{plain('link')} Открыть t.me", url=f"https://t.me/{name}")],
        [B(text=f"{plain('target')} Мои ловушки", callback_data="traps")],
    ])


# --------------------------------- премиум ----------------------------------
def premium_text(active_until: int | None) -> str:
    status = (f"\n\n{e('ok')} <b>Подписка активна до {ts_date(active_until)}</b>"
              if active_until else "")
    return (
        f"{e('gem')} <b>Premium</b> — {config.PREMIUM_PRICE_STARS} {e('star')} в месяц\n\n"
        f"{e('bolt')} Лимиты поиска выше в десятки раз\n"
        f"{e('crown')} Много Premium-поисков читаемых ников\n"
        f"{e('chart')} Автопоиск ника по нужной цене\n"
        f"{e('target')} До {config.TRAP_SLOTS['premium']} ловушек вместо {config.TRAP_SLOTS['free']}"
        + status
    )


def premium_kb(url: str | None, active: bool) -> KB:
    rows = []
    label = "Продлить" if active else "Оформить"
    if url:
        rows.append([B(text=f"{plain('star')} {label} за {config.PREMIUM_PRICE_STARS} ⭐", url=url)])
    else:
        rows.append([B(text=f"{plain('star')} {label} за {config.PREMIUM_PRICE_STARS} ⭐", callback_data="buy")])
    rows.append([B(text=f"{plain('home')} В меню", callback_data="menu")])
    return kb(rows)


# --------------------------------- автопоиск --------------------------------
def auto_text(cfg, premium: bool) -> str:
    if not premium:
        return (f"{e('chart')} <b>Автопоиск</b>\n\nБот сам ищет ники нужной длины, выставленные на "
                f"Fragment дешевле вашей цены, и присылает уведомление.\n\n"
                f"{e('lock')} Доступно с подпиской Premium.")
    if cfg and cfg["active"]:
        return (f"{e('chart')} <b>Автопоиск включён</b>\n\n"
                f"Длина: <b>{cfg['length']}</b> букв\nМаксимальная цена: <b>{cfg['max_price']:g} TON</b>\n\n"
                f"Как только найдётся подходящий ник, пришлю уведомление.")
    return (f"{e('chart')} <b>Автопоиск</b>\n\nВыберите длину ника, затем максимальную цену на Fragment.")


def auto_kb(cfg, premium: bool) -> KB:
    if not premium:
        return kb([[B(text=f"{plain('gem')} Получить Premium", callback_data="premium")],
                   [B(text=f"{plain('home')} В меню", callback_data="menu")]])
    rows = []
    if cfg and cfg["active"]:
        rows.append([B(text=f"{plain('stop')} Остановить", callback_data="auto_stop")])
    rows.append([B(text="5 букв", callback_data="auto_len:5"), B(text="6 букв", callback_data="auto_len:6")])
    rows.append([B(text=f"{plain('home')} В меню", callback_data="menu")])
    return kb(rows)


def auto_price_kb(length: int) -> KB:
    rows, row = [], []
    for p in config.AUTO_PRICE_PRESETS:
        row.append(B(text=f"до {p} TON", callback_data=f"auto_set:{length}:{p}"))
        if len(row) == 3:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([B(text=f"{plain('back')} Назад", callback_data="auto")])
    return kb(rows)


def auto_hit_text(name: str, price: float | None) -> str:
    p = f"{price:g} TON" if price is not None else "цена на странице"
    return (f"{e('chart')} <b>Автопоиск нашёл ник</b>\n\n"
            f"{e('user')} <code>@{name}</code>\n{e('money')} Цена: <b>{p}</b>")


def auto_hit_kb(name: str) -> KB:
    return kb([[B(text=f"{plain('link')} Открыть на Fragment", url=f"https://fragment.com/username/{name}"),
                B(text=f"{plain('copy')} Скопировать", copy_text=CopyTextButton(text=f"@{name}"))]])
