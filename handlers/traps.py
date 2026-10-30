import re

from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton as B, Message

import config
import ui
from core import answer, checker, db, edit, tier
from emojis import e, plain

router = Router()

NAME_RE = re.compile(r"^[a-z][a-z0-9_]{4,31}$")


class TrapAdd(StatesGroup):
    waiting = State()


def valid_name(n: str) -> bool:
    return bool(NAME_RE.match(n)) and not n.endswith("_") and "__" not in n


async def render(uid: int):
    traps = await db.traps_list(uid)
    t = await tier(uid)
    return await ui.traps_text(uid, t, traps), ui.traps_kb(traps)


@router.callback_query(F.data == "traps")
async def cb_traps(cb: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await cb.answer()
    text, kb = await render(cb.from_user.id)
    await edit(cb.message, text, kb)


@router.callback_query(F.data == "trap_add")
async def cb_add(cb: CallbackQuery, state: FSMContext) -> None:
    uid = cb.from_user.id
    slots = config.TRAP_SLOTS[await tier(uid)]
    if await db.traps_count(uid) >= slots:
        await cb.answer("Слоты закончились", show_alert=True)
        return
    await cb.answer()
    await state.set_state(TrapAdd.waiting)
    await edit(
        cb.message,
        f"{e('target')} <b>Новая ловушка</b>\n\nОтправьте занятый ник, можно сразу несколько: "
        f"через пробел, запятую или с новой строки.\nНапример: <code>@durov telegram</code>",
        ui.kb([[B(text=f"{plain('back')} Отмена", callback_data="traps")]]),
    )


@router.message(StateFilter(TrapAdd.waiting), F.text)
async def got_names(msg: Message, state: FSMContext) -> None:
    uid = msg.from_user.id
    raw = [x.strip().lstrip("@").lower() for x in re.split(r"[\s,;]+", msg.text) if x.strip()]
    names = list(dict.fromkeys(raw))[:50]
    if not names:
        await answer(msg, "Не вижу ников. Отправьте хотя бы один, например <code>@durov</code>.")
        return

    slots = config.TRAP_SLOTS[await tier(uid)]
    used = await db.traps_count(uid)
    added, free_now, invalid, no_slots, dup = [], [], [], [], []

    good = [n for n in names if valid_name(n)]
    invalid = [n for n in names if not valid_name(n)]
    results = {r.name: r for r in await checker.check_many(good, use_cache=False)} if good else {}

    for n in good:
        r = results[n]
        if r.free:
            free_now.append(n)
        elif used >= slots:
            no_slots.append(n)
        elif await db.trap_add(uid, n):
            used += 1
            added.append(n)
        else:
            dup.append(n)

    lines = []
    if added:
        lines.append(f"{e('ok')} Поставил ловушки: " + ", ".join(f"<code>@{n}</code>" for n in added))
    if free_now:
        lines.append(f"{e('fire')} Уже свободны, забирайте скорее: " + ", ".join(f"<code>@{n}</code>" for n in free_now))
    if dup:
        lines.append(f"{e('info')} Уже в ловушках: " + ", ".join(f"@{n}" for n in dup))
    if no_slots:
        lines.append(f"{e('lock')} Нет слотов для: " + ", ".join(f"@{n}" for n in no_slots))
    if invalid:
        lines.append(f"{e('bad')} Некорректные (5-32 символа, латиница, цифры, _): " + ", ".join(f"@{n}" for n in invalid))

    await state.clear()
    await answer(msg, "\n".join(lines))
    text, kb = await render(uid)
    await answer(msg, text, kb)


@router.callback_query(F.data.startswith("trap_del:"))
async def cb_del(cb: CallbackQuery) -> None:
    await db.trap_del(cb.from_user.id, int(cb.data.split(":")[1]))
    await cb.answer("Удалено")
    text, kb = await render(cb.from_user.id)
    await edit(cb.message, text, kb)


@router.callback_query(F.data == "trap_clear")
async def cb_clear(cb: CallbackQuery) -> None:
    await db.trap_clear(cb.from_user.id)
    await cb.answer("Все ловушки удалены")
    text, kb = await render(cb.from_user.id)
    await edit(cb.message, text, kb)
