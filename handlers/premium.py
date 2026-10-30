import logging
import time

from aiogram import Bot, F, Router
from aiogram.types import CallbackQuery, LabeledPrice, Message, PreCheckoutQuery

import config
import ui
from core import answer, db, edit, fmt_left, remaining, send_to, tier
from emojis import e

router = Router()
log = logging.getLogger("premium")


async def _link(bot: Bot) -> str | None:
    try:
        return await bot.create_invoice_link(
            title="Premium на 1 месяц",
            description="Высокие лимиты поиска, автопоиск и до 300 ловушек",
            payload="premium_month",
            currency="XTR",
            prices=[LabeledPrice(label="Premium", amount=config.PREMIUM_PRICE_STARS)],
            subscription_period=config.PREMIUM_PERIOD_SECONDS,
        )
    except Exception as ex:
        log.warning("create_invoice_link: %s", ex)
        return None


async def show_premium(msg: Message, uid: int, bot: Bot, edit_mode: bool) -> None:
    t = await tier(uid)
    if t == "admin":
        text = (f"{e('gem')} <b>Premium</b>\n\n{e('crown')} Вы администратор: все возможности "
                f"включены навсегда, оплата не нужна.")
        kb = ui.back_kb()
    else:
        until = await db.premium_until(uid)
        active = until > time.time()
        text = ui.premium_text(until if active else None)
        kb = ui.premium_kb(await _link(bot), active)
    if edit_mode:
        await edit(msg, text, kb)
    else:
        await answer(msg, text, kb)


@router.callback_query(F.data == "premium")
async def cb_premium(cb: CallbackQuery, bot: Bot) -> None:
    await cb.answer()
    await show_premium(cb.message, cb.from_user.id, bot, True)


@router.callback_query(F.data == "buy")
async def cb_buy(cb: CallbackQuery, bot: Bot) -> None:
    await cb.answer("Не удалось создать счёт, попробуйте позже", show_alert=True)


@router.pre_checkout_query()
async def pre_checkout(q: PreCheckoutQuery) -> None:
    await q.answer(ok=True)


@router.message(F.successful_payment)
async def paid(msg: Message) -> None:
    sp = msg.successful_payment
    uid = msg.from_user.id
    await db.payment_add(uid, sp.telegram_payment_charge_id, sp.total_amount)
    exp = getattr(sp, "subscription_expiration_date", None)
    if exp:
        await db.set_premium_until(uid, int(exp))
        until = int(exp)
    else:
        until = await db.add_premium_days(uid, 30)
    await answer(
        msg,
        f"{e('party')} <b>Premium активирован!</b>\n\nДействует до <b>{ui.ts_date(until)}</b>. "
        f"Подписка продлевается автоматически, отключить можно в настройках Telegram.",
        ui.back_kb(),
    )


@router.callback_query(F.data == "profile")
async def cb_profile(cb: CallbackQuery) -> None:
    uid = cb.from_user.id
    await cb.answer()
    t = await tier(uid)
    until = await db.premium_until(uid)
    if t == "admin":
        status = f"{e('crown')} Администратор"
    elif t == "premium":
        status = f"{e('gem')} Premium до {ui.ts_date(until)}"
    else:
        status = f"{e('user')} Обычный аккаунт"
    slots = config.TRAP_SLOTS[t]
    lines = [f"{e('user')} <b>Профиль</b>", "", f"Статус: {status}", f"ID: <code>{uid}</code>", ""]
    for key, title in (("i5", "5 букв"), ("i6", "6 букв"), ("p5", "5 букв Premium"), ("p6", "6 букв Premium")):
        lines.append(f"{e('hourglass')} {title}: осталось <b>{fmt_left(await remaining(uid, key))}</b>")
    lines.append(f"{e('target')} Ловушки: <b>{await db.traps_count(uid)}/{slots}</b>")
    await edit(cb.message, "\n".join(lines), ui.back_kb())
