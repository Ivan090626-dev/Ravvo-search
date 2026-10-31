from aiogram import F, Router
from aiogram.types import CallbackQuery

import ui
from core import db, edit, is_premium

router = Router()


async def render(uid: int):
    cfg = await db.auto_get(uid)
    prem = await is_premium(uid)
    return ui.auto_text(cfg, prem), ui.auto_kb(cfg, prem)


@router.callback_query(F.data == "auto")
async def cb_auto(cb: CallbackQuery) -> None:
    await cb.answer()
    text, kb = await render(cb.from_user.id)
    await edit(cb.message, text, kb)


@router.callback_query(F.data.regexp(r"^auto_len:[56]$"))
async def cb_len(cb: CallbackQuery) -> None:
    if not await is_premium(cb.from_user.id):
        await cb.answer("Нужна подписка Premium", show_alert=True)
        return
    length = int(cb.data.split(":")[1])
    await cb.answer()
    await edit(cb.message, f"Выберите максимальную цену для ников из <b>{length}</b> букв:",
               ui.auto_price_kb(length))


@router.callback_query(F.data.regexp(r"^auto_set:[56]:\d+$"))
async def cb_set(cb: CallbackQuery) -> None:
    if not await is_premium(cb.from_user.id):
        await cb.answer("Нужна подписка Premium", show_alert=True)
        return
    _, l, p = cb.data.split(":")
    await db.auto_set(cb.from_user.id, int(l), float(p), 1)
    await cb.answer("Автопоиск включён")
    text, kb = await render(cb.from_user.id)
    await edit(cb.message, text, kb)


@router.callback_query(F.data == "auto_stop")
async def cb_stop(cb: CallbackQuery) -> None:
    await db.auto_stop(cb.from_user.id)
    await cb.answer("Остановлен")
    text, kb = await render(cb.from_user.id)
    await edit(cb.message, text, kb)
