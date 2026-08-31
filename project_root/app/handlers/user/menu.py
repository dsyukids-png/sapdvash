from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.database.models import User, Message as DBMessage
from app.keyboards.callbacks import MenuCB
from app.keyboards.inline import get_main_menu_kb, get_back_kb
from app.keyboards.builders import build_share_link_kb
from app.texts.templates import Texts
from app.texts.emojis import Emojis
from app.services.crypto import generate_personal_token
from app.config import config

router = Router()

@router.callback_query(MenuCB.filter(F.action == "main"))
async def cb_main_menu(query: CallbackQuery, state: FSMContext):
    await state.clear()
    message = query.message
    if not isinstance(message, Message):
        return
    await message.edit_text(
        text=Texts.MAIN_MENU,
        reply_markup=get_main_menu_kb()
    )

@router.callback_query(MenuCB.filter(F.action == "link"))
async def cb_my_link(query: CallbackQuery, db_user: User, bot: Bot):
    await query.answer()
    me = await bot.get_me()
    message = query.message
    if not isinstance(message, Message):
        return
    bot_username = (me.username or config.BOT_USERNAME).lstrip("@")
    await message.edit_text(
        text=Texts.MY_LINK.format(link=f"https://t.me/{bot_username}?start={db_user.personal_token}"),
        reply_markup=build_share_link_kb(bot_username, db_user.personal_token)
    )

@router.callback_query(MenuCB.filter(F.action == "help"))
async def cb_help(query: CallbackQuery):
    message = query.message
    if not isinstance(message, Message):
        return
    await message.edit_text(
        text=Texts.HELP,
        reply_markup=get_back_kb("main")
    )

@router.callback_query(MenuCB.filter(F.action == "inbox"))
async def cb_inbox(query: CallbackQuery, db_user: User, session: AsyncSession):
    result = await session.execute(
        select(func.count(DBMessage.id)).where(DBMessage.recipient_id == db_user.id)
    )
    msg_count = result.scalar()

    text = (
        f"{Emojis.INBOX} <b>Твои сообщения</b>\n\n"
        f"Все новые анонимные сообщения приходят прямо в этот чат от лица бота.\n\n"
        f"{Emojis.STATS} Всего получено сообщений: <b>{msg_count}</b>"
    )

    message = query.message
    if not isinstance(message, Message):
        return
    await message.edit_text(
        text=text,
        reply_markup=get_back_kb("main")
    )

@router.callback_query(MenuCB.filter(F.action == "settings"))
async def cb_settings(query: CallbackQuery, db_user: User):
    text = (
        f"{Emojis.SETTINGS} <b>Настройки профиля</b>\n\n"
        f"{Emojis.USER} Telegram ID: <code>{db_user.telegram_id}</code>\n"
        f"{Emojis.ADMIN} Роль в системе: <b>{db_user.role}</b>\n"
        f"{Emojis.LOCK} Статус бана: <b>{'Активен' if db_user.is_banned else 'Не активен'}</b>\n"
        f"{Emojis.LINK} Персональная ссылка: <code>активна</code>\n\n"
        f"{Emojis.SUCCESS} Здесь можно быстро управлять профилем и безопасностью."
    )
    builder = InlineKeyboardBuilder()
    if not db_user.is_banned:
        builder.button(text="Сбросить ссылку", callback_data=MenuCB(action="reset_token").pack(), icon_custom_emoji_id=Emojis.UNLOCK.custom_id)
        builder.button(text="Назад", callback_data=MenuCB(action="main").pack(), icon_custom_emoji_id=Emojis.BACK.custom_id)
        builder.adjust(1)
    message = query.message
    if not isinstance(message, Message):
        return
    await message.edit_text(
        text=text,
        reply_markup=builder.as_markup() if not db_user.is_banned else None,
    )

@router.callback_query(MenuCB.filter(F.action == "reset_token"))
async def cb_reset_token(query: CallbackQuery, db_user: User, session: AsyncSession):
    db_user.personal_token = generate_personal_token()
    await session.commit()
    await query.answer("Персональная ссылка успешно сброшена!", show_alert=True)
