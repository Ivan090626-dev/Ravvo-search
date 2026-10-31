import asyncio
import re

from aiogram import Bot, F, Router
from aiogram.filters import Command, CommandObject
from aiogram.types import LinkPreviewOptions, Message

import subscription

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
        "/emojis — список имён эмодзи и текущих id\n"
        "/channels — обязательные каналы подписки\n"
        "/addchannel <code>@канал</code> или <code>-100… ссылка-приглашение</code> — добавить обязательный канал\n"
        "/delchannel <code>@канал или id</code> — убрать канал\n\n"
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


# ----------------------- обязательные каналы подписки -----------------------
def _chat_ref(arg: str):
    arg = arg.strip()
    m = re.match(r"(?:https?://)?t\.me/([A-Za-z0-9_]{4,})/?$", arg)
    if m:
        return "@" + m.group(1)
    if re.fullmatch(r"-?\d+", arg):
        return int(arg)
    return arg if arg.startswith("@") else "@" + arg


@router.message(Command("channels"))
async def cmd_channels(msg: Message) -> None:
    chs = await db.channels_list()
    if not chs:
        await answer(msg, "Обязательных каналов нет. Добавить: /addchannel <code>@канал</code>")
        return
    lines = "\n".join(f"• {c['title']} — <code>{c['chat_id']}</code>\n  {c['link']}" for c in chs)
    await answer(msg, f"<b>Обязательные каналы</b>\n\n{lines}\n\nУбрать: /delchannel <code>id</code>",
                 link_preview_options=LinkPreviewOptions(is_disabled=True))


@router.message(Command("addchannel"))
async def cmd_addchannel(msg: Message, command: CommandObject, bot: Bot) -> None:
    parts = (command.args or "").split()
    if not parts:
        await answer(msg, (
            "Формат: /addchannel <code>@канал</code>\n"
            "Для приватного канала: /addchannel <code>-1001234567890 https://t.me/+ссылка</code>\n\n"
            "Бот должен быть <b>администратором</b> канала, иначе не сможет проверять подписку."
        ))
        return
    try:
        chat = await bot.get_chat(_chat_ref(parts[0]))
    except Exception as ex:
        await answer(msg, f"Не нашёл канал: {ex}\nБот должен быть добавлен в канал как администратор.")
        return
    try:
        me = await bot.get_chat_member(chat.id, bot.id)
        if me.status not in ("administrator", "creator"):
            raise RuntimeError("бот не администратор")
    except Exception:
        await answer(msg, "Сделайте бота администратором этого канала и повторите команду.")
        return
    if chat.username:
        link = f"https://t.me/{chat.username}"
    elif len(parts) > 1 and parts[1].startswith("http"):
        link = parts[1]
    else:
        try:
            link = await bot.export_chat_invite_link(chat.id)
        except Exception:
            await answer(msg, "У канала нет публичного имени. Добавьте ссылку: "
                              f"/addchannel <code>{chat.id} https://t.me/+ссылка</code>")
            return
    await db.channel_add(chat.id, chat.title or str(chat.id), link)
    subscription._ok_cache.clear()
    await answer(msg, f"Добавил: <b>{chat.title}</b>. Теперь без подписки бот не работает.")


@router.message(Command("delchannel"))
async def cmd_delchannel(msg: Message, command: CommandObject, bot: Bot) -> None:
    if not command.args:
        await answer(msg, "Формат: /delchannel <code>@канал или id</code> (список: /channels)")
        return
    ref = _chat_ref(command.args.split()[0])
    chat_id = ref if isinstance(ref, int) else None
    if chat_id is None:
        try:
            chat_id = (await bot.get_chat(ref)).id
        except Exception:
            await answer(msg, "Не нашёл такой канал. Посмотрите id в /channels.")
            return
    if chat_id not in {c["chat_id"] for c in await db.channels_list()}:
        await answer(msg, "Этого канала нет в списке: /channels")
        return
    await db.channel_del(chat_id)
    subscription._ok_cache.clear()
    await answer(msg, "Канал убран из обязательных.")
