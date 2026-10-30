from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

import ui
from core import answer, edit

router = Router()


@router.message(CommandStart())
@router.message(Command("menu"))
async def cmd_start(msg: Message, state: FSMContext) -> None:
    await state.clear()
    await answer(msg, await ui.menu_text(msg.from_user.id), ui.menu_kb())


@router.callback_query(F.data == "menu")
async def cb_menu(cb: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await cb.answer()
    await edit(cb.message, await ui.menu_text(cb.from_user.id), ui.menu_kb())
