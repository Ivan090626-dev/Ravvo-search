"""Фоновые задачи: ловушки (каждые 15 мин) и автопоиск."""
import asyncio
import logging

from aiogram import Bot

import config
import ui
import cards
from core import card_send, checker, db, is_premium, send_to
from emojis import e
from generator import dictionary_words

log = logging.getLogger("workers")


async def traps_loop(bot: Bot) -> None:
    await asyncio.sleep(20)
    while True:
        try:
            names = await db.trap_names()
            for i in range(0, len(names), 20):
                chunk = names[i: i + 20]
                for r in await checker.check_many(chunk, use_cache=False):
                    if not r.free:
                        continue
                    no = await db.next_card_no()
                    png = await asyncio.to_thread(cards.render_card, r.name, no)
                    for uid in await db.trap_users(r.name):
                        await card_send(
                            bot, uid, png,
                            f"{e('bell')} <b>Ловушка сработала!</b>\n\n"
                            f"{e('user')} <code>@{r.name}</code> освободился.\n"
                            f"{e('ok')} Telegram — свободен\n{e('ok')} Fragment — не на аукционе\n\n"
                            f"Скорее занимайте.",
                            ui.trap_hit_kb(r.name),
                        )
                    await db.trap_remove_name(r.name)
        except Exception:
            log.exception("traps_loop")
        await asyncio.sleep(config.TRAP_INTERVAL)


async def auto_loop(bot: Bot) -> None:
    await asyncio.sleep(30)
    while True:
        try:
            cfgs = await db.auto_active()
            if cfgs:
                listing = await checker.fragment_listing()
                for cfg in cfgs:
                    if not await is_premium(cfg["user_id"]):
                        await db.auto_stop(cfg["user_id"])
                        await send_to(bot, cfg["user_id"], f"{e('lock')} Подписка Premium закончилась, автопоиск остановлен.")
                        continue
                    for name, price in listing:
                        if len(name) != cfg["length"] or not name.isalpha():
                            continue
                        if price is None or price > cfg["max_price"]:
                            continue
                        if await db.auto_was_notified(cfg["user_id"], name):
                            continue
                        await db.auto_mark(cfg["user_id"], name)
                        no = await db.next_card_no()
                        png = await asyncio.to_thread(cards.render_card, name, no, "sale", price)
                        await card_send(bot, cfg["user_id"], png, ui.auto_hit_text(name, price), ui.auto_hit_kb(name))
        except Exception:
            log.exception("auto_loop")
        await asyncio.sleep(config.AUTO_CYCLE_SECONDS)
