"""Обязательная подписка на каналы: проверка при каждом действии пользователя."""
import logging
import time

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, InlineKeyboardButton as B, InlineKeyboardMarkup as KB, Message

import config
from core import answer, db
from emojis import e

log = logging.getLogger("subscription")

CACHE_TTL = 30  # секунд: реже дёргаем Telegram, но отписка замечается быстро
_ok_cache: dict[int, float] = {}
_OK_STATUSES = {"creator", "administrator", "member"}


def channel_url(ch) -> str:
    return ch["link"]


async def missing(bot, uid: int, use_cache: bool = True) -> list:
    """Каналы, на которые пользователь не подписан."""
    if uid in config.ADMIN_IDS:
        return []
    if use_cache and time.time() - _ok_cache.get(uid, 0) < CACHE_TTL:
        return []
    out = []
    for ch in await db.channels_list():
        try:
            m = await bot.get_chat_member(ch["chat_id"], uid)
            ok = m.status in _OK_STATUSES or (m.status == "restricted" and getattr(m, "is_member", False))
        except Exception as ex:
            # бот не админ канала / канал удалён: не блокируем всех из-за настройки
            log.warning("Не могу проверить подписку на %s (%s): %s", ch["title"], ch["chat_id"], ex)
            continue
        if not ok:
            out.append(ch)
    if not out:
        _ok_cache[uid] = time.time()
    else:
        _ok_cache.pop(uid, None)
    return out


def sub_text(chs: list) -> str:
    lines = "\n".join(f"{e('link')} {c['title']}" for c in chs)
    return (
        f"{e('lock')} <b>Чтобы пользоваться ботом, подпишитесь на каналы</b>\n\n"
        f"{lines}\n\n"
        "После подписки нажмите «Проверить подписку»."
    )


def sub_kb(chs: list) -> KB:
    rows = [[B(text=f"➕ {c['title']}", url=channel_url(c))] for c in chs]
    rows.append([B(text="✅ Проверить подписку", callback_data="chk")])
    return KB(inline_keyboard=rows)


class SubscriptionMiddleware(BaseMiddleware):
    """Не пускает к боту тех, кто не подписан на обязательные каналы (админов не трогает)."""

    async def __call__(self, handler, event, data):
        u = data.get("event_from_user")
        if not u or u.is_bot or u.id in config.ADMIN_IDS:
            return await handler(event, data)
        if isinstance(event, Message):
            if event.chat.type != "private" or event.successful_payment:
                return await handler(event, data)
        elif isinstance(event, CallbackQuery):
            if event.data == "chk":
                return await handler(event, data)
        else:
            return await handler(event, data)

        miss = await missing(data["bot"], u.id)
        if not miss:
            return await handler(event, data)

        if isinstance(event, CallbackQuery):
            await event.answer("Сначала подпишитесь на каналы", show_alert=False)
            msg = event.message
        else:
            msg = event
        if msg:
            await answer(msg, sub_text(miss), sub_kb(miss))
        return None
