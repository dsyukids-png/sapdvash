import asyncio

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import ContentType, Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import User
from app.handlers.states import MessagingState
from app.keyboards.inline import get_main_menu_kb
from app.services.sender import queue_anonymous_media_group, send_anonymous_message
from app.texts.templates import Texts

router = Router()


@router.message(
    MessagingState.waiting_for_anonymous_msg,
    F.content_type.in_({
        ContentType.TEXT,
        ContentType.PHOTO,
        ContentType.VIDEO,
        ContentType.VOICE,
        ContentType.VIDEO_NOTE,
        ContentType.STICKER,
        ContentType.DOCUMENT,
        ContentType.ANIMATION,
    }),
)
async def process_anonymous_message(
    message: Message,
    state: FSMContext,
    db_user: User,
    session: AsyncSession,
):
    data = await state.get_data()
    recipient_id = data.get("recipient_id")

    if not recipient_id:
        await state.clear()
        await message.answer(Texts.ERR_USER_NOT_FOUND, reply_markup=get_main_menu_kb())
        return

    result = await session.execute(select(User).where(User.id == recipient_id))
    recipient = result.scalar_one_or_none()

    if not recipient:
        await state.clear()
        await message.answer(Texts.ERR_USER_NOT_FOUND, reply_markup=get_main_menu_kb())
        return

    media_group_id = getattr(message, "media_group_id", None)
    if media_group_id:
        photos = getattr(message, "photo", None) or []
        if not photos:
            return

        await queue_anonymous_media_group(
            session=session,
            sender=db_user,
            recipient=recipient,
            first_message=message,
            media_group_id=media_group_id,
            file_ids=[photo.file_id for photo in photos],
            caption=(message.caption or message.text or "").strip(),
            state=state,
        )
        return

    success = await send_anonymous_message(
        session=session,
        sender=db_user,
        recipient=recipient,
        original_message=message,
    )

    if success:
        await message.answer(Texts.MESSAGE_SENT_SUCCESS, reply_markup=get_main_menu_kb())
    else:
        await message.answer(
            "Не удалось отправить сообщение. Возможно, получатель заблокировал бота.",
            reply_markup=get_main_menu_kb(),
        )

    await state.clear()