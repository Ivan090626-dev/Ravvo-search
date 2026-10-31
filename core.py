"""Общие объекты и утилиты, которыми пользуются все модули."""
import time
from typing import Optional

from aiogram.exceptions import TelegramBadRequest
from aiogram.types import BufferedInputFile, CallbackQuery, InlineKeyboardMarkup, InputMediaPhoto, Message

import config
import emojis
from checker import Checker
from db import DB

db = DB(config.DB_PATH)
checker = Checker()


async def tier(uid: int) -> str:
    if uid in config.ADMIN_IDS:
        return "admin"
    return "premium" if await db.premium_until(uid) > time.time() else "free"


async def is_premium(uid: int) -> bool:
    return (await tier(uid)) != "free"


async def remaining(uid: int, key: str) -> Optional[int]:
    """Сколько поисков осталось сегодня. None = без лимита."""
    limit = config.LIMITS[await tier(uid)][key]
    if limit is None:
        return None
    return max(0, limit - await db.usage_get(uid, key))


def fmt_left(v: Optional[int]) -> str:
    return "∞" if v is None else str(v)


# ----- безопасная отправка: если премиум-эмодзи не прошли, повторяем с обычными -----
def _is_emoji_error(ex: TelegramBadRequest) -> bool:
    m = str(ex).lower()
    return "emoji" in m or "entities" in m or "parse entities" in m


async def answer(msg: Message, text: str, kb: Optional[InlineKeyboardMarkup] = None, **kw) -> Message:
    try:
        return await msg.answer(text, reply_markup=kb, **kw)
    except TelegramBadRequest as ex:
        if _is_emoji_error(ex):
            return await msg.answer(emojis.strip_custom(text), reply_markup=kb, **kw)
        raise


async def edit(msg: Message, text: str, kb: Optional[InlineKeyboardMarkup] = None, **kw) -> None:
    if msg.photo:  # сообщение-карточка: заменяем на обычное текстовое
        try:
            await msg.delete()
        except Exception:
            pass
        await answer(msg, text, kb, **kw)
        return
    try:
        await msg.edit_text(text, reply_markup=kb, **kw)
    except TelegramBadRequest as ex:
        m = str(ex).lower()
        if "not modified" in m:
            return
        if _is_emoji_error(ex):
            try:
                await msg.edit_text(emojis.strip_custom(text), reply_markup=kb, **kw)
            except TelegramBadRequest as ex2:
                if "not modified" not in str(ex2).lower():
                    raise
            return
        raise


async def send_to(bot, uid: int, text: str, kb: Optional[InlineKeyboardMarkup] = None, **kw) -> bool:
    try:
        try:
            await bot.send_message(uid, text, reply_markup=kb, **kw)
        except TelegramBadRequest as ex:
            if _is_emoji_error(ex):
                await bot.send_message(uid, emojis.strip_custom(text), reply_markup=kb, **kw)
            else:
                raise
        return True
    except Exception:
        return False


# ----------------------------- карточки-картинки -----------------------------
async def status(msg: Message, text: str, kb: Optional[InlineKeyboardMarkup] = None) -> None:
    """Меняет текст сообщения, не убирая картинку (если она есть)."""
    if not msg.photo:
        await edit(msg, text, kb)
        return
    try:
        await msg.edit_caption(caption=text, reply_markup=kb)
    except TelegramBadRequest as ex:
        if _is_emoji_error(ex):
            await msg.edit_caption(caption=emojis.strip_custom(text), reply_markup=kb)
        elif "not modified" not in str(ex).lower():
            raise


async def card_replace(msg: Message, png: bytes, caption: str, kb: InlineKeyboardMarkup) -> None:
    """Показывает карточку на месте текущего сообщения."""
    file = BufferedInputFile(png, filename="ravvo.png")
    if msg.photo:
        for cap in (caption, emojis.strip_custom(caption)):
            try:
                await msg.edit_media(InputMediaPhoto(media=file, caption=cap, parse_mode="HTML"), reply_markup=kb)
                return
            except TelegramBadRequest as ex:
                if not _is_emoji_error(ex):
                    break
    else:
        try:
            await msg.delete()
        except Exception:
            pass
    for cap in (caption, emojis.strip_custom(caption)):
        try:
            await msg.answer_photo(BufferedInputFile(png, filename="ravvo.png"), caption=cap, reply_markup=kb)
            return
        except TelegramBadRequest as ex:
            if not _is_emoji_error(ex):
                raise


async def card_send(bot, uid: int, png: bytes, caption: str, kb: Optional[InlineKeyboardMarkup] = None) -> bool:
    for cap in (caption, emojis.strip_custom(caption)):
        try:
            await bot.send_photo(uid, BufferedInputFile(png, filename="ravvo.png"), caption=cap, reply_markup=kb)
            return True
        except TelegramBadRequest as ex:
            if not _is_emoji_error(ex):
                break
        except Exception:
            break
    return await send_to(bot, uid, caption, kb)
