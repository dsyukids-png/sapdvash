from datetime import datetime, timedelta, timezone

from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InputMediaPhoto
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.database.models import User, SupportTicket
from app.keyboards.callbacks import MenuCB, SupportCB
from app.keyboards.inline import get_back_kb
from app.handlers.states import MessagingState, SupportState
from app.texts.templates import Texts
from app.texts.emojis import Emojis

router = Router()


def build_support_user_reply_kb(ticket_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text="Ответить",
        callback_data=SupportCB(action="user_reply", ticket_id=ticket_id).pack(),
    )
    builder.adjust(1)
    return builder.as_markup()


async def get_open_ticket_for_user(session: AsyncSession, user_id: int) -> SupportTicket | None:
    result = await session.execute(
        select(SupportTicket)
        .where(SupportTicket.user_id == user_id, SupportTicket.status == "open")
        .order_by(SupportTicket.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def get_last_ticket_for_user(session: AsyncSession, user_id: int) -> SupportTicket | None:
    result = await session.execute(
        select(SupportTicket)
        .where(SupportTicket.user_id == user_id)
        .order_by(SupportTicket.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


MEDIA_GROUP_CACHE: dict[str, dict] = {}


async def _flush_ticket_media_group(bot, chat_id: int, media_group_id: str, caption: str | None):
    group_data = MEDIA_GROUP_CACHE.pop(media_group_id, None)
    if not group_data:
        return

    media = []
    for idx, item in enumerate(group_data.get("items", [])):
        media.append(
            InputMediaPhoto(
                media=item["file_id"],
                caption=caption if idx == 0 and caption else None,
                parse_mode="HTML",
            )
        )
    if media:
        await bot.send_media_group(chat_id=chat_id, media=media)


async def _schedule_ticket_media_group_flush(bot, chat_id: int, media_group_id: str, caption: str | None):
    await asyncio.sleep(0.8)
    await _flush_ticket_media_group(bot, chat_id, media_group_id, caption)


async def send_ticket_media_group(bot, chat_id: int, message: Message, caption: str):
    photos = getattr(message, "photo", None) or []
    group_id = getattr(message, "media_group_id", None)
    if group_id:
        group_data = MEDIA_GROUP_CACHE.setdefault(group_id, {"chat_id": chat_id, "items": []})
        group_data["items"].append({"file_id": photos[-1].file_id})
        if not group_data.get("scheduled"):
            group_data["scheduled"] = True
            asyncio.create_task(_schedule_ticket_media_group_flush(bot, chat_id, group_id, caption if caption and caption.strip() else None))
        return True

    if photos:
        photo = photos[-1]
        await bot.send_photo(
            chat_id=chat_id,
            photo=photo.file_id,
            caption=caption if caption and caption.strip() else None,
            parse_mode="HTML",
        )
        return True
    return False


async def notify_admins_about_ticket(
    message: Message,
    ticket: SupportTicket,
    user: User,
    title: str,
    session: AsyncSession,
):
    admins_result = await session.execute(
        select(User).where(User.role.in_(["admin", "owner", "moderator"]))
    )
    admins = admins_result.scalars().all()

    content_text = (message.text or message.caption or "").strip()
    admin_text = (
        f"{Emojis.TICKET} <b>{title} #{ticket.id}</b>\n\n"
        f"{Emojis.USER} Пользователь: <code>{user.telegram_id}</code>\n"
    )
    if content_text:
        admin_text += f"{Emojis.MAIL} {content_text}"
    admin_keyboard = InlineKeyboardBuilder()
    admin_keyboard.button(
        text="Ответить",
        callback_data=SupportCB(action="reply", ticket_id=ticket.id).pack(),
        icon_custom_emoji_id=Emojis.REPLY.custom_id,
    )
    admin_keyboard.button(
        text="Закрыть",
        callback_data=SupportCB(action="close", ticket_id=ticket.id).pack(),
        icon_custom_emoji_id=Emojis.SUCCESS.custom_id,
    )
    admin_keyboard.adjust(2)

    for admin in admins:
        try:
            if message.content_type == "text":
                await message.bot.send_message(
                    admin.telegram_id,
                    admin_text,
                    reply_markup=admin_keyboard.as_markup(),
                )
                continue

            if await send_ticket_media_group(message.bot, admin.telegram_id, message, admin_text):
                continue

            await message.copy_to(
                admin.telegram_id,
                caption=admin_text,
                reply_markup=admin_keyboard.as_markup(),
            )
        except Exception:
            continue


@router.callback_query(MenuCB.filter(F.action == "support"))
async def cb_support_menu(query: CallbackQuery, state: FSMContext, db_user: User, session: AsyncSession):
    now = datetime.now(timezone.utc)
    if db_user.support_banned_until and db_user.support_banned_until <= now:
        db_user.support_banned_until = None
        await session.commit()

    if db_user.support_banned_until and db_user.support_banned_until > now:
        left = int((db_user.support_banned_until - now).total_seconds())
        hours = max(1, (left + 3599) // 3600)
        await query.answer(f"Писать в поддержку можно только через {hours} ч.", show_alert=True)
        return

    open_ticket = await get_open_ticket_for_user(session, db_user.id)
    if open_ticket:
        await state.update_data(ticket_id=open_ticket.id)
    await state.set_state(SupportState.waiting_for_ticket_text)
    await query.message.edit_text(
        text=Texts.SUPPORT_PROMPT,
        reply_markup=get_back_kb("main")
    )


@router.message(SupportState.waiting_for_ticket_text)
async def process_support_ticket(
    message: Message,
    state: FSMContext,
    db_user: User,
    session: AsyncSession,
):
    now = datetime.now(timezone.utc)
    if db_user.support_banned_until and db_user.support_banned_until <= now:
        db_user.support_banned_until = None
        await session.commit()
    if db_user.support_banned_until and db_user.support_banned_until > now:
        left = int((db_user.support_banned_until - now).total_seconds())
        hours = max(1, (left + 3599) // 3600)
        await message.answer(f"{Emojis.BLOCK} Писать в поддержку можно только через {hours} ч. Текущий запрет действует до {db_user.support_banned_until.strftime('%d.%m.%Y %H:%M')}.")
        return

    open_ticket = await get_open_ticket_for_user(session, db_user.id)
    if open_ticket is None:
        recent_tickets = await session.execute(
            select(SupportTicket).where(
                SupportTicket.user_id == db_user.id,
                SupportTicket.created_at >= now - timedelta(hours=24),
            )
        )
        recent_count = len(recent_tickets.scalars().all())
        if recent_count >= 3:
            db_user.support_spam_level += 1
            ban_hours = 24 * (2 ** max(0, db_user.support_spam_level - 1))
            db_user.support_banned_until = now + timedelta(hours=ban_hours)
            await session.commit()
            await message.answer(
                f"{Emojis.BLOCK} <b>Ты временно ограничен в поддержке</b>\n\n"
                f"Слишком много обращений за последние 24 часа. Писать можно будет через <b>{ban_hours} ч.</b>"
            )
            return

        ticket_text = (message.text or message.caption or "").strip()
        ticket = SupportTicket(user_id=db_user.id, text=ticket_text, status="open")
        session.add(ticket)
        await session.commit()
        await session.refresh(ticket)
        await notify_admins_about_ticket(message, ticket, db_user, "Новое обращение", session)
        await state.update_data(ticket_id=ticket.id)
        await message.answer(
            f"{Texts.TICKET_CREATED}\n\n"
            f"{Emojis.SUPPORT} Можешь отправить ещё одно сообщение сюда в любой момент."
        )
        return

    if open_ticket.status != "open":
        await message.answer(Texts.TICKET_CLOSED)
        return

    ticket_text = (message.text or message.caption or "").strip()
    if ticket_text:
        open_ticket.text = f"{open_ticket.text}\n\n---\n{ticket_text}"
    await session.commit()
    await notify_admins_about_ticket(message, open_ticket, db_user, "Новый ответ в тикете", session)
    await state.update_data(ticket_id=open_ticket.id)
    await message.answer(
        f"{Emojis.SUCCESS} <b>Сообщение отправлено в поддержку.</b>\n\n"
        f"{Emojis.SUPPORT} Тикет #{open_ticket.id} продолжает жить — поддержка сможет ответить тебе здесь же."
    )


@router.callback_query(SupportCB.filter(F.action == "reply"))
async def cb_ticket_reply(
    query: CallbackQuery,
    callback_data: SupportCB,
    state: FSMContext,
    db_user: User,
    session: AsyncSession,
):
    if db_user.role not in ["admin", "owner", "moderator"]:
        await query.answer("Доступ запрещен", show_alert=True)
        return

    ticket = await session.get(SupportTicket, callback_data.ticket_id)
    if not ticket or ticket.status == "closed":
        await query.answer("Тикет уже закрыт или не найден", show_alert=True)
        return

    await state.update_data(ticket_id=ticket.id)
    await state.set_state(SupportState.waiting_for_ticket_reply)
    await query.answer()
    if isinstance(query.message, Message):
        await query.message.answer(
            f"{Emojis.REPLY} <b>Ответ на тикет #{ticket.id}</b>\n\n"
            "Отправь текст, фото, GIF, видео, стикер, файл или голосовое сообщение."
        )


@router.callback_query(SupportCB.filter(F.action == "user_reply"))
async def cb_user_ticket_reply(
    query: CallbackQuery,
    callback_data: SupportCB,
    state: FSMContext,
    db_user: User,
    session: AsyncSession,
):
    ticket = await session.get(SupportTicket, callback_data.ticket_id)
    if not ticket:
        await query.answer("Тикет не найден", show_alert=True)
        return
    if ticket.user_id != db_user.id:
        await query.answer("Этот тикет не твоё обращение", show_alert=True)
        return
    if ticket.status == "closed":
        await query.answer("Тикет закрыт, дальше писать нельзя", show_alert=True)
        return

    await state.update_data(ticket_id=ticket.id)
    await state.set_state(SupportState.waiting_for_user_ticket_reply)
    await query.answer()
    if isinstance(query.message, Message):
        await query.message.answer(
            f"{Emojis.REPLY} <b>Ответ в тикет #{ticket.id}</b>\n\n"
            "Напиши сообщение, которое уйдёт поддержке."
        )


@router.message(SupportState.waiting_for_ticket_reply)
async def process_ticket_reply(
    message: Message,
    state: FSMContext,
    db_user: User,
    session: AsyncSession,
):
    if db_user.role not in ["admin", "owner", "moderator"]:
        await state.clear()
        return

    data = await state.get_data()
    ticket = await session.get(SupportTicket, data.get("ticket_id"))
    if not ticket or ticket.status == "closed":
        await state.clear()
        await message.answer(f"{Emojis.ERROR} Тикет уже закрыт или не найден.")
        return

    user = await session.get(User, ticket.user_id)
    if not user:
        await state.clear()
        await message.answer(f"{Emojis.ERROR} Пользователь тикета не найден.")
        return

    try:
        response_caption = (
            f"{Emojis.REPLY} <b>Ответ поддержки по тикету #{ticket.id}</b>\n\n"
        )
        if message.content_type == "text":
            await message.bot.send_message(
                user.telegram_id,
                response_caption + (message.text or ""),
                reply_markup=build_support_user_reply_kb(ticket.id),
            )
        elif await send_ticket_media_group(message.bot, user.telegram_id, message, response_caption):
            pass
        else:
            await message.copy_to(
                user.telegram_id,
                caption=response_caption + (message.caption or ""),
                reply_markup=build_support_user_reply_kb(ticket.id),
            )
        ticket_text = (message.text or message.caption or "").strip()
        ticket.text = f"{ticket.text}\n\n---\n{response_caption}{ticket_text}" if ticket_text else ticket.text
        await session.commit()
        await message.answer(f"{Emojis.SUCCESS} Ответ отправлен пользователю.")
    except Exception:
        await message.answer(f"{Emojis.ERROR} Не удалось доставить ответ.")
    finally:
        await state.clear()


@router.message(SupportState.waiting_for_user_ticket_reply)
async def process_user_ticket_reply(
    message: Message,
    state: FSMContext,
    db_user: User,
    session: AsyncSession,
):
    data = await state.get_data()
    ticket_id = data.get("ticket_id")
    if not ticket_id:
        await state.clear()
        await message.answer(Texts.ERR_OUTDATED)
        return

    ticket = await session.get(SupportTicket, ticket_id)
    if not ticket:
        await state.clear()
        await message.answer(f"{Emojis.ERROR} Тикет не найден.")
        return
    if ticket.user_id != db_user.id:
        await state.clear()
        await message.answer(f"{Emojis.ERROR} Это не твой тикет.")
        return
    if ticket.status == "closed":
        await state.clear()
        await message.answer(Texts.TICKET_CLOSED)
        return

    ticket_text = message.text or message.caption or f"{Emojis.MAIL} Вложение: {message.content_type}"
    ticket.text = f"{ticket.text}\n\n---\n{ticket_text}"
    await session.commit()

    admins = (await session.execute(select(User).where(User.role.in_(["admin", "owner", "moderator"]))) ).scalars().all()
    for admin in admins:
        try:
            caption = f"{Emojis.TICKET} <b>Новый ответ в тикете #{ticket.id}</b>\n\n{Emojis.USER} Пользователь: <code>{db_user.telegram_id}</code>\n"
            if ticket_text:
                caption += f"{Emojis.MAIL} {ticket_text}"
            if message.content_type == "text":
                await message.bot.send_message(
                    admin.telegram_id,
                    caption,
                    reply_markup=build_support_user_reply_kb(ticket.id),
                )
            elif await send_ticket_media_group(message.bot, admin.telegram_id, message, caption):
                pass
            else:
                await message.copy_to(
                    admin.telegram_id,
                    caption=caption,
                    reply_markup=build_support_user_reply_kb(ticket.id),
                )
        except Exception:
            continue

    await state.clear()
    await message.answer(
        f"{Emojis.SUCCESS} <b>Сообщение отправлено в поддержку.</b>\n\n"
        f"{Emojis.SUPPORT} Тикет #{ticket.id} продолжает обсуждаться."
    )


@router.callback_query(SupportCB.filter(F.action == "close"))
async def cb_ticket_close(
    query: CallbackQuery,
    callback_data: SupportCB,
    db_user: User,
    session: AsyncSession,
):
    if db_user.role not in ["admin", "owner", "moderator"]:
        await query.answer("Доступ запрещен", show_alert=True)
        return

    ticket = await session.get(SupportTicket, callback_data.ticket_id)
    if not ticket:
        await query.answer("Тикет не найден", show_alert=True)
        return

    ticket.status = "closed"
    await session.commit()
    await query.answer("Тикет закрыт")
    if isinstance(query.message, Message):
        await query.message.edit_reply_markup(reply_markup=None)


@router.message(F.chat.type == "private")
async def process_active_support_followup(
    message: Message,
    state: FSMContext,
    db_user: User,
    session: AsyncSession,
):
    if db_user.role in ["admin", "owner", "moderator"]:
        return

    current_state = await state.get_state()
    if current_state in {
        MessagingState.waiting_for_anonymous_msg.state,
        SupportState.waiting_for_ticket_text.state,
        SupportState.waiting_for_ticket_reply.state,
        SupportState.waiting_for_user_ticket_reply.state,
    }:
        return
    if getattr(message, "media_group_id", None):
        return

    ticket = await get_open_ticket_for_user(session, db_user.id)
    if ticket is None:
        last_ticket = await get_last_ticket_for_user(session, db_user.id)
        if last_ticket and last_ticket.status == "closed":
            await message.answer(Texts.TICKET_CLOSED)
        return

    ticket_text = (message.text or message.caption or "").strip()
    if ticket_text:
        ticket.text = f"{ticket.text}\n\n---\n{ticket_text}"
    await session.commit()
    await notify_admins_about_ticket(message, ticket, db_user, "Новый ответ в тикете", session)
    await message.answer(
        f"{Emojis.SUCCESS} <b>Сообщение добавлено в тикет #{ticket.id}.</b>\n\n"
        f"{Emojis.SUPPORT} Поддержка ответит тебе тут же, когда будет готова."
    )