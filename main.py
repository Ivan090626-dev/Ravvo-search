import asyncio
import logging
import sys

from aiogram import BaseMiddleware, Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

import config
import workers
from core import checker, db
from handlers import routers


class UserMiddleware(BaseMiddleware):
    """Запоминает пользователя при любом действии."""

    async def __call__(self, handler, event, data):
        u = data.get("event_from_user")
        if u and not u.is_bot:
            await db.upsert_user(u.id, u.username, u.full_name)
        return await handler(event, data)


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    if not config.BOT_TOKEN:
        sys.exit("Укажите BOT_TOKEN в файле .env")

    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    await db.init()
    await checker.start()

    bot = Bot(config.BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    checker.bot = bot
    dp = Dispatcher(storage=MemoryStorage())
    dp.update.outer_middleware(UserMiddleware())
    for r in routers:
        dp.include_router(r)

    tasks = [asyncio.create_task(workers.traps_loop(bot)), asyncio.create_task(workers.auto_loop(bot))]
    try:
        import emojis
        done, _ = await emojis.load_packs(bot)
        if done:
            logging.info("Премиум-эмодзи подгружены: %s", done)
        me = await bot.get_me()
        logging.info("Бот @%s запущен", me.username)
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        for t in tasks:
            t.cancel()
        await checker.close()
        await db.close()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
