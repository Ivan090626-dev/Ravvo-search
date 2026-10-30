import asyncio

from aiogram import Bot, F, Router
from aiogram.filters import Command, CommandObject
from aiogram.types import Message

import config
import emojis
from core import answer, db, send_to

router = Router()
router.message.filter(F.from_user.id.in_(config.ADMIN_IDS))


@router.message(Command("admin"))
async def cmd_admin(msg: Message) -> None:
    await answer(msg, (
        "<b>Команды администратора</b>\n\n"
        "/stats — статистика\n"
        "/grant <code>id дней</code> — выдать Premium (отрицательное число забирает)\n"
        "/broadcast <code>текст</code> — рассылка всем\n"
        "/addpack <code>ссылка на набор эмодзи</code> — подключить премиум-эмодзи автоматически\n"
        "/setemoji <code>имя id</code> — задать премиум-эмодзи (id или <code>-</code> чтобы убрать)\n"
        "/emojis — список имён эмодзи и текущих id\n\n"
        "Чтобы узнать id премиум-эмодзи, отправьте боту сообщение с ним, он ответит id."
    ))


@router.message(Command("stats"))
async def cmd_stats(msg: Message) -> None:
    s = await db.stats()
    await answer(msg, (
        "<b>Статистика</b>\n"
        f"Пользователей: {s['users']}\nPremium: {s['premium']}\n"
        f"Ловушек: {s['traps']}\nАвтопоисков: {s['auto']}\nЗвёзд получено: {s['stars']}"
    ))


@router.message(Command("grant"))
async def cmd_grant(msg: Message, command: CommandObject) -> None:
    try:
        uid, days = (int(x) for x in (command.args or "").split())
    except ValueError:
        await answer(msg, "Формат: /grant <code>id дней</code>")
        return
    until = await db.add_premium_days(uid, days)
    await answer(msg, f"Готово. Premium у {uid} до {until} (unix).")


@router.message(Command("broadcast"))
async def cmd_broadcast(msg: Message, command: CommandObject, bot: Bot) -> None:
    if not command.args:
        await answer(msg, "Формат: /broadcast <code>текст</code>")
        return
    ok = 0
    for uid in await db.all_user_ids():
        ok += await send_to(bot, uid, command.args)
        await asyncio.sleep(0.05)
    await answer(msg, f"Отправлено: {ok}")


@router.message(Command("addpack"))
async def cmd_addpack(msg: Message, command: CommandObject, bot: Bot) -> None:
    if not command.args:
        await answer(msg, "Формат: /addpack <code>https://t.me/addemoji/ИМЯ</code>\n"
                          "Бот возьмёт из набора эмодзи, которые совпадают с его обычными, и заменит их на премиум.")
        return
    done, missing = await emojis.load_packs(bot, command.args.split()[0])
    if not done:
        await answer(msg, "Не нашёл подходящих эмодзи. Проверьте ссылку: набор должен быть именно набором "
                          "кастомных эмодзи (t.me/addemoji/...).")
        return
    text = f"Готово: подключено премиум-эмодзи — <b>{done}</b>."
    if missing:
        text += "\nНе нашлось в наборе: " + " ".join(emojis.plain(k) for k in missing)
        text += "\nДобавьте ещё один набор командой /addpack, он дополнит недостающие."
    await answer(msg, text)


@router.message(Command("emojis"))
async def cmd_emojis(msg: Message) -> None:
    lines = [f"{emojis.plain(k)} <code>{k}</code> → {emojis._ids.get(k, '—')}" for k in emojis.FALLBACK]
    await answer(msg, "\n".join(lines))


@router.message(Command("setemoji"))
async def cmd_setemoji(msg: Message, command: CommandObject) -> None:
    parts = (command.args or "").split()
    if len(parts) != 2 or parts[0] not in emojis.FALLBACK:
        await answer(msg, "Формат: /setemoji <code>имя id</code>. Список имён: /emojis")
        return
    emojis.set_id(parts[0], parts[1])
    await answer(msg, f"Ок: {parts[0]} → {parts[1]}")


def _has_custom_emoji(msg: Message) -> bool:
    return any(en.type == "custom_emoji" for en in (msg.entities or []))


@router.message(_has_custom_emoji)
async def emoji_id_helper(msg: Message) -> None:
    ids = [en.custom_emoji_id for en in msg.entities if en.type == "custom_emoji"]
    await answer(msg, "ID премиум-эмодзи:\n" + "\n".join(f"<code>{i}</code>" for i in ids))
