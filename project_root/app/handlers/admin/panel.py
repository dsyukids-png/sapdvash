from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, delete
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.database.models import User, Message as DBMessage, SupportTicket, Log, Ban
from app.keyboards.callbacks import MenuCB, AdminCB, SupportCB
from app.texts.emojis import Emojis
from app.texts.templates import Texts
from app.keyboards.inline import get_main_menu_kb
from app.handlers.states import AdminState
from app.config import config
from app.services.crypto import generate_personal_token

router = Router()
FULL_ADMIN_ROLES = ["admin", "owner"]
STAFF_ROLES = FULL_ADMIN_ROLES + ["moderator"]

def get_admin_menu_kb(role: str = "admin") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Статистика", callback_data=AdminCB(action="stats").pack(), icon_custom_emoji_id=Emojis.STATS.custom_id)
    builder.button(text="Пользователи", callback_data=AdminCB(action="users").pack(), icon_custom_emoji_id=Emojis.USER.custom_id)
    if role not in ["vip"]:
        builder.button(text="Поддержка", callback_data=AdminCB(action="tickets").pack(), icon_custom_emoji_id=Emojis.TICKET.custom_id)
        builder.button(text="Логи", callback_data=AdminCB(action="logs").pack(), icon_custom_emoji_id=Emojis.LOGS.custom_id)
    builder.button(text="В главное меню", callback_data=MenuCB(action="main").pack(), icon_custom_emoji_id=Emojis.BACK.custom_id)
    if role in FULL_ADMIN_ROLES:
        builder.button(text="Выдать бан", callback_data=AdminCB(action="ask_ban").pack(), icon_custom_emoji_id=Emojis.BLOCK.custom_id)
        builder.button(text="Выдать VIP", callback_data=AdminCB(action="ask_vip").pack(), icon_custom_emoji_id=Emojis.SUCCESS.custom_id)
        builder.button(text="Выдать админку", callback_data=AdminCB(action="ask_admin").pack(), icon_custom_emoji_id=Emojis.ADMIN.custom_id)
        builder.button(text="Снять бан", callback_data=AdminCB(action="ask_unban").pack(), icon_custom_emoji_id=Emojis.UNLOCK.custom_id)
        builder.button(text="Снять VIP", callback_data=AdminCB(action="ask_remove_vip").pack(), icon_custom_emoji_id=Emojis.UNLOCK.custom_id)
        builder.button(text="Снять админку", callback_data=AdminCB(action="ask_remove_admin").pack(), icon_custom_emoji_id=Emojis.UNLOCK.custom_id)
        builder.adjust(2, 2, 1, 2, 2, 2, 1)
    elif role == "vip":
        builder.adjust(2, 1)
    else:
        builder.adjust(2, 2, 1)
    return builder.as_markup()

@router.message(F.text == "/admin")
async def cmd_admin(message: Message, db_user: User):
    if db_user.role not in STAFF_ROLES:
        await message.answer(f"{Emojis.ERROR} У вас нет доступа к этой команде.")
        return

    await message.answer(
        f"{Emojis.ADMIN} <b>Админ-панель</b>\n\nВыберите нужный раздел:",
        reply_markup=get_admin_menu_kb(db_user.role)
    )

@router.callback_query(AdminCB.filter(F.action == "main"))
async def cb_admin_home(query: CallbackQuery, db_user: User):
    if db_user.role not in STAFF_ROLES:
        await query.answer("Доступ запрещен", show_alert=True)
        return

    message = query.message
    if not isinstance(message, Message):
        return

    await message.edit_text(
        text=f"{Emojis.ADMIN} <b>Админ-панель</b>\n\nВыберите нужный раздел:",
        reply_markup=get_admin_menu_kb(db_user.role)
    )

@router.callback_query(AdminCB.filter(F.action == "stats"))
async def cb_admin_stats(query: CallbackQuery, session: AsyncSession, db_user: User):
    if db_user.role not in STAFF_ROLES:
        return

    total_users = (await session.execute(select(func.count(User.id)))).scalar()
    banned_users = (await session.execute(select(func.count(User.id)).where(User.is_banned == True))).scalar()
    total_messages = (await session.execute(select(func.count(DBMessage.id)))).scalar()
    open_tickets = (await session.execute(select(func.count(SupportTicket.id)).where(SupportTicket.status == "open"))).scalar()

    text = (
        f"{Emojis.STATS} <b>Статистика бота</b>\n\n"
        f"{Emojis.USER} Всего пользователей: <b>{total_users}</b>\n"
        f"{Emojis.BLOCK} Заблокированных: <b>{banned_users}</b>\n"
        f"{Emojis.MAIL} Всего сообщений: <b>{total_messages}</b>\n"
        f"{Emojis.TICKET} Открытых тикетов: <b>{open_tickets}</b>"
    )
    
    builder = InlineKeyboardBuilder()
    builder.button(text="Назад в админку", callback_data=AdminCB(action="main").pack(), icon_custom_emoji_id=Emojis.BACK.custom_id)

    message = query.message
    if not isinstance(message, Message):
        return

    await message.edit_text(text=text, reply_markup=builder.as_markup())


ACCESS_ACTIONS = {
    "ask_ban": "ban",
    "ask_vip": "vip",
    "ask_admin": "admin",
    "ask_unban": "unban",
    "ask_remove_vip": "remove_vip",
    "ask_remove_admin": "remove_admin",
}


def get_access_confirmation_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text="Да",
        callback_data=AdminCB(action="confirm_access").pack(),
        icon_custom_emoji_id=Emojis.SUCCESS.custom_id,
    )
    builder.button(
        text="Нет",
        callback_data=AdminCB(action="cancel_access").pack(),
        icon_custom_emoji_id=Emojis.ERROR.custom_id,
    )
    builder.adjust(2)
    return builder.as_markup()


@router.callback_query(AdminCB.filter(F.action.in_(ACCESS_ACTIONS.keys())))
async def cb_access_action(
    query: CallbackQuery,
    callback_data: AdminCB,
    state,
    db_user: User,
):
    if db_user.role not in FULL_ADMIN_ROLES:
        await query.answer("Нужны права администратора", show_alert=True)
        return

    action = ACCESS_ACTIONS[callback_data.action]
    await state.update_data(access_action=action)
    await state.set_state(AdminState.waiting_for_user_id)
    await query.answer()
    if isinstance(query.message, Message):
        await query.message.answer(
            f"{Emojis.USER} Введи Telegram ID пользователя для действия <b>{action}</b>."
        )


@router.message(AdminState.waiting_for_user_id)
async def process_access_user_id(
    message: Message,
    state,
    db_user: User,
    session: AsyncSession,
):
    if db_user.role not in FULL_ADMIN_ROLES:
        await state.clear()
        return

    try:
        telegram_id = int((message.text or "").strip())
    except ValueError:
        await message.answer(f"{Emojis.ERROR} Введи корректный числовой Telegram ID.")
        return

    if telegram_id == db_user.telegram_id or telegram_id == config.OWNER_ID:
        await state.clear()
        await message.answer(f"{Emojis.ERROR} Нельзя изменять права владельца или свои права.")
        return

    data = await state.get_data()
    target = (await session.execute(select(User).where(User.telegram_id == telegram_id))).scalar_one_or_none()
    action = data.get("access_action")
    if not target and action in {"unban", "remove_vip", "remove_admin"}:
        await state.clear()
        await message.answer(f"{Emojis.ERROR} Пользователь не найден в базе бота.")
        return
    if not target:
        target = User(
            telegram_id=telegram_id,
            role="user",
            personal_token=generate_personal_token(),
        )
        session.add(target)
        await session.flush()

    await state.update_data(target_user_id=target.id, target_telegram_id=telegram_id)
    await state.set_state(AdminState.waiting_for_user_id)
    await message.answer(
        f"{Emojis.WARN} Подтвердить действие <b>{action}</b> для пользователя "
        f"<code>{telegram_id}</code>?",
        reply_markup=get_access_confirmation_kb(),
    )


@router.callback_query(AdminCB.filter(F.action == "confirm_access"))
async def cb_confirm_access(
    query: CallbackQuery,
    state,
    db_user: User,
    session: AsyncSession,
    bot: Bot,
):
    if db_user.role not in FULL_ADMIN_ROLES:
        await query.answer("Нужны права администратора", show_alert=True)
        return

    data = await state.get_data()
    action = data.get("access_action")
    target = await session.get(User, data.get("target_user_id"))
    if not target or not action:
        await state.clear()
        await query.answer("Данные действия устарели", show_alert=True)
        return
    if target.telegram_id == config.OWNER_ID or target.telegram_id == db_user.telegram_id:
        await state.clear()
        await query.answer("Нельзя изменять права владельца или свои права", show_alert=True)
        return

    notice = Texts.ACCESS_REMOVED_NOTICE
    markup = get_main_menu_kb()
    if action == "ban":
        target.is_banned = True
        if not (await session.execute(select(Ban).where(Ban.user_id == target.id))).scalar_one_or_none():
            session.add(Ban(user_id=target.id, admin_id=db_user.id, reason="Выдан администратором"))
        notice = Texts.BANNED_SCREEN
        markup = None
    elif action == "unban":
        target.is_banned = False
        await session.execute(delete(Ban).where(Ban.user_id == target.id))
        notice = Texts.UNBANNED_NOTICE
    elif action == "vip":
        target.role = "vip"
        notice = Texts.VIP_NOTICE
    elif action == "admin":
        target.role = "admin"
        notice = Texts.ADMIN_NOTICE
    elif action == "remove_vip":
        if target.role == "vip":
            target.role = "user"
    elif action == "remove_admin":
        if target.role == "admin":
            target.role = "user"

    await session.commit()
    try:
        await bot.send_message(target.telegram_id, notice, reply_markup=markup)
    except Exception:
        pass
    await state.clear()
    await query.answer("Готово")
    if isinstance(query.message, Message):
        await query.message.edit_reply_markup(reply_markup=None)


@router.callback_query(AdminCB.filter(F.action == "cancel_access"))
async def cb_cancel_access(query: CallbackQuery, state):
    await state.clear()
    await query.answer("Действие отменено")
    if isinstance(query.message, Message):
        await query.message.edit_reply_markup(reply_markup=None)


async def user_is_reachable(bot: Bot, telegram_id: int) -> bool:
    try:
        me = await bot.get_me()
        await bot.get_chat_member(chat_id=telegram_id, user_id=me.id)
        return True
    except Exception:
        return False


@router.callback_query(AdminCB.filter(F.action == "users"))
async def cb_admin_users(query: CallbackQuery, session: AsyncSession, db_user: User, bot: Bot):
    if db_user.role not in STAFF_ROLES:
        return

    result = await session.execute(select(User).order_by(User.id.desc()).limit(20))
    users = result.scalars().all()
    visible_users = []
    for user in users:
        if await user_is_reachable(bot, user.telegram_id):
            visible_users.append(user)

    users_list = "\n".join([
        f"{Emojis.USER} ID: <code>{u.telegram_id}</code> | @{u.username or 'нет'} | Бан: {'Да' if u.is_banned else 'Нет'}"
        for u in visible_users
    ]) or "Пользователей с активным доступом к боту нет."

    text = f"{Emojis.USER} <b>Пользователи с доступом к боту:</b>\n\n{users_list}"

    builder = InlineKeyboardBuilder()
    builder.button(text="Назад в админку", callback_data=AdminCB(action="main").pack(), icon_custom_emoji_id=Emojis.BACK.custom_id)
    builder.adjust(1)

    message = query.message
    if not isinstance(message, Message):
        return

    await message.edit_text(text=text, reply_markup=builder.as_markup())


@router.callback_query(AdminCB.filter(F.action == "tickets"))
async def cb_admin_tickets(query: CallbackQuery, session: AsyncSession, db_user: User):
    if db_user.role not in ["admin", "owner", "moderator"]:
        return

    result = await session.execute(select(SupportTicket).order_by(SupportTicket.created_at.desc()).limit(20))
    tickets = result.scalars().all()

    if not tickets:
        tickets_text = "История тикетов пуста."
    else:
        ticket_items = []
        for ticket in tickets:
            status = "Открыт" if ticket.status == "open" else "Закрыт"
            status_emoji = Emojis.SUCCESS if ticket.status == "open" else Emojis.BLOCK
            ticket_items.append(
                f"{status_emoji} Тикет #{ticket.id} | {status}\n"
                f"{Emojis.SUPPORT} {ticket.text[:220]}{'...' if len(ticket.text) > 220 else ''}"
            )
        tickets_text = "\n\n".join(ticket_items)

    text = f"{Emojis.TICKET} <b>История тикетов поддержки:</b>\n\n{tickets_text}"

    builder = InlineKeyboardBuilder()
    for ticket in tickets:
        if ticket.status == "open":
            builder.button(
                text=f"Ответить на тикет #{ticket.id}",
                callback_data=SupportCB(action="reply", ticket_id=ticket.id).pack(),
                icon_custom_emoji_id=Emojis.REPLY.custom_id,
            )
    builder.button(text="Назад в админку", callback_data=AdminCB(action="main").pack(), icon_custom_emoji_id=Emojis.BACK.custom_id)
    builder.adjust(*([1] * max(1, len([t for t in tickets if t.status == "open"]))), 1)

    message = query.message
    if not isinstance(message, Message):
        return

    await message.edit_text(text=text, reply_markup=builder.as_markup())

@router.callback_query(AdminCB.filter(F.action == "logs"))
async def cb_admin_logs(query: CallbackQuery, session: AsyncSession, db_user: User):
    if db_user.role not in ["admin", "owner", "moderator"]:
        return

    result = await session.execute(select(Log).order_by(Log.created_at.desc()).limit(10))
    logs = result.scalars().all()

    logs_text = "\n".join([f"• [{log.created_at.strftime('%H:%M')}] ID {log.admin_id}: {log.action}" for log in logs]) or "Логов пока нет."

    text = f"{Emojis.LOGS} <b>Последние лог-записи:</b>\n\n{logs_text}"

    builder = InlineKeyboardBuilder()
    builder.button(text="Назад в админку", callback_data=AdminCB(action="main").pack(), icon_custom_emoji_id=Emojis.BACK.custom_id)

    message = query.message
    if not isinstance(message, Message):
        return

    await message.edit_text(text=text, reply_markup=builder.as_markup())
