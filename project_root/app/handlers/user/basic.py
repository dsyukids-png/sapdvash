from aiogram import Router, F
from aiogram.filters import CommandStart, CommandObject
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database.models import User
from app.texts.templates import Texts
from app.keyboards.inline import get_main_menu_kb, get_back_kb
from app.handlers.states import MessagingState

router = Router()

@router.message(CommandStart())
async def cmd_start(
    message: Message, 
    command: CommandObject, 
    db_user: User, 
    session: AsyncSession, 
    state: FSMContext
):
    # Сбрасываем любые предыдущие состояния (очистка FSM)
    await state.clear()

    if db_user.is_banned:
        await message.answer(Texts.BANNED_SCREEN)
        return
    
    args = command.args
    
    # Если перешли по ссылке с токеном
    if args:
        if args == db_user.personal_token:
            await message.answer("Вы не можете отправить анонимное сообщение самому себе.")
            return

        # Ищем владельца ссылки в БД
        result = await session.execute(select(User).where(User.personal_token == args))
        recipient = result.scalar_one_or_none()
        
        if not recipient:
            await message.answer(Texts.ERR_USER_NOT_FOUND)
            return
            
        # Запоминаем ID получателя в FSM и переводим в состояние ожидания сообщения
        await state.update_data(recipient_id=recipient.id)
        await state.set_state(MessagingState.waiting_for_anonymous_msg)
        
        await message.answer(
            Texts.SEND_PROMPT,
            reply_markup=get_back_kb("main") # Кнопка отмены
        )
        return

    # Если обычный старт без параметров - показываем главное меню
    await message.answer(
        Texts.WELCOME + "\n\n" + Texts.MAIN_MENU,
        reply_markup=get_main_menu_kb()
    )