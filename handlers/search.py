import asyncio
import time

from aiogram import F, Router
from aiogram.types import CallbackQuery

import config
import ui
import cards
from core import card_replace, checker, db, remaining, status
from generator import Seen, candidates

router = Router()
_active: set[int] = set()
_seen = Seen()


async def find_free(uid: int, length: int, mode: str) -> str | None:
    timeout = config.SEARCH_TIMEOUT_INSTANT if mode == "i" else config.SEARCH_TIMEOUT_PREMIUM
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        cands = [
            c for c in candidates(length, mode, config.BATCH_SIZE * 2)
            if not _seen.has(uid, c) and not checker.is_cached_taken(c)
        ][: config.BATCH_SIZE]
        if not cands:
            await asyncio.sleep(0.2)
            continue
        results = await checker.check_many(cands)
        for r in results:
            if r.free:
                _seen.add(uid, r.name)
                return r.name
        if all(r.has_error for r in results):  # скорее всего ограничение запросов
            await asyncio.sleep(2)
    return None


@router.callback_query(F.data.regexp(r"^s:[56]:[ip]$"))
async def on_search(cb: CallbackQuery) -> None:
    _, l, mode = cb.data.split(":")
    length, uid = int(l), cb.from_user.id
    key = f"{mode}{l}"

    left = await remaining(uid, key)
    if left is not None and left <= 0:
        await cb.answer()
        await status(cb.message, ui.limit_text(length, mode), ui.limit_kb())
        return
    if uid in _active:
        await cb.answer("Уже ищу, секунду…")
        return

    _active.add(uid)
    await cb.answer()
    try:
        await status(cb.message, ui.searching_text(length, mode))
        name = await find_free(uid, length, mode)
        if name:
            await db.usage_inc(uid, key)
            no = await db.next_card_no()
            png = await asyncio.to_thread(cards.render_card, name, no)
            await card_replace(cb.message, png, await ui.found_text(uid, name, length, mode),
                               ui.found_kb(name, length, mode))
        else:
            await status(cb.message, ui.not_found_text(length, mode), ui.not_found_kb(length, mode))
    finally:
        _active.discard(uid)
