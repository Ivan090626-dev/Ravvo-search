from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

import ui
import subscription
from core import edit

router = Router()


@router.callback_query(F.data == "chk")
async def cb_check(cb: CallbackQuery, state: FSMContext) -> None:
    miss = await subscription.missing(cb.bot, cb.from_user.id, use_cache=False)
    if miss:
        await cb.answer("Вы подписались не на все каналы", show_alert=True)
        await edit(cb.message, subscription.sub_text(miss), subscription.sub_kb(miss))
        return
    await state.clear()
    await cb.answer("Готово!")
    await edit(cb.message, await ui.menu_text(cb.from_user.id), ui.menu_kb())
