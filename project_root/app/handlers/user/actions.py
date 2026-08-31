from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database.models import User, Ban
from app.keyboards.callbacks import MsgActionCB, AdminCB
from app.keyboards.builders import build_message_action_kb
from app.handlers.states import MessagingState
from app.texts.templates import Texts
from app.texts.emojis import Emojis

router = Router()

@router.callback_query(MsgActionCB.filter(F.action == "reply"))
async def cb_reply_message(query: CallbackQuery, callback_data: MsgActionCB, state: FSMContext):
    await state.update_data(
        target_sender_db_id=callback_data.sender_id,
        original_msg_id=callback_data.message_id
    )
    await state.set_state(MessagingState.waiting_for_reply)
    message = query.message
    if not isinstance(message, Message):
        return
    await message.answer(Texts.REPLY_PROMPT)
    await query.answer()

@router.message(MessagingState.waiting_for_reply)
async def process_reply_message(
    message: Message, 
    state: FSMContext, 
    db_user: User, 
    session: AsyncSession
):
    data = await state.get_data()
    target_sender_db_id = data.get("target_sender_db_id")
    
    if not target_sender_db_id:
        await state.clear()
        await message.answer(Texts.ERR_OUTDATED)
        return

    result = await session.execute(select(User).where(User.id == target_sender_db_id))
    original_sender = result.scalar_one_or_none()
    
    if not original_sender:
        await state.clear()
        await message.answer(Texts.ERR_USER_NOT_FOUND)
        return

    try:
        bot = message.bot
        if bot is None:
            await message.answer(f"{Emojis.ERROR} Не удалось доставить ответ.")
            return

        reply_markup = build_message_action_kb(message_id=0, sender_db_id=db_user.id)
        if message.text:
            await bot.send_message(
                chat_id=original_sender.telegram_id,
                text=Texts.REPLY_RECEIVED.format(content=message.text),
                reply_markup=reply_markup,
            )
        else:
            await message.copy_to(
                chat_id=original_sender.telegram_id,
                caption=f"{Emojis.REPLY} <b>Ответ на анонимное сообщение:</b>\n\n{message.caption}" if message.caption else "",
                reply_markup=reply_markup,
            )
        await message.answer(f"{Emojis.SUCCESS} Ответ успешно отправлен!")
    except Exception:
        await message.answer(f"{Emojis.ERROR} Не удалось доставить ответ (пользователь мог заблокировать бота).")

    await state.clear()

@router.callback_query(MsgActionCB.filter(F.action == "block"))
async def cb_block_sender(query: CallbackQuery, callback_data: MsgActionCB, db_user: User, session: AsyncSession, bot: Bot):
    if db_user.role == "vip":
        await query.answer("VIP может только видеть отправителя сообщения.", show_alert=True)
        return

    target_user = await session.get(User, callback_data.sender_id)
    existing_ban = await session.execute(
        select(Ban).where(Ban.user_id == callback_data.sender_id)
    )
    if not existing_ban.scalar_one_or_none():
        new_ban = Ban(
            user_id=callback_data.sender_id,
            admin_id=db_user.id,
            reason="Заблокирован получателем"
        )
        session.add(new_ban)
        
        if target_user:
            target_user.is_banned = True
            
        await session.commit()

        if target_user:
            try:
                await bot.send_message(
                    target_user.telegram_id,
                    Texts.BANNED_SCREEN,
                )
            except Exception:
                pass
    
    await query.answer("Пользователь заблокирован.", show_alert=True)
    message = query.message
    if not isinstance(message, Message):
        return
    try:
        await message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass

@router.callback_query(MsgActionCB.filter(F.action == "report"))
async def cb_report_message(query: CallbackQuery):
    await query.answer("⚠️ Жалоба успешно отправлена администрации.", show_alert=True)
    message = query.message
    if not isinstance(message, Message):
        return
    try:
        await message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass

@router.callback_query(AdminCB.filter(F.action == "reveal"))
async def cb_admin_reveal(query: CallbackQuery, callback_data: AdminCB, db_user: User):
    if db_user.role not in ["admin", "owner", "moderator", "vip"]:
        await query.answer("У тебя нет прав администратора!", show_alert=True)
        return
        
    target_tg_id = callback_data.target_id
    await query.answer(
        f"🛡 Данные отправителя:\nTelegram ID: {target_tg_id}", 
        show_alert=True
    )