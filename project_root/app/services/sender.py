import asyncio
import logging
from typing import Any

from aiogram import Bot
from aiogram.types import InputMediaPhoto, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import Message as DBMessage, User
from app.keyboards.callbacks import AdminCB, MsgActionCB
from app.texts.emojis import Emojis

MEDIA_GROUP_CACHE: dict[tuple[int, int, str], dict[str, Any]] = {}
MEDIA_GROUP_TASKS: dict[tuple[int, int, str], asyncio.Task] = {}
MEDIA_GROUP_LOCK = asyncio.Lock()


def _dedupe_file_ids(file_ids: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for file_id in file_ids:
        if not file_id or file_id in seen:
            continue
        seen.add(file_id)
        ordered.append(file_id)
    return ordered


async def queue_anonymous_media_group(
    session: AsyncSession,
    sender: User,
    recipient: User,
    first_message: Message,
    media_group_id: str,
    file_ids: list[str],
    caption: str,
    state: Any | None = None,
) -> None:
    key = (sender.id, recipient.id, media_group_id)
    deduped = _dedupe_file_ids(file_ids)

    async with MEDIA_GROUP_LOCK:
        group = MEDIA_GROUP_CACHE.setdefault(
            key,
            {
                "session": session,
                "sender": sender,
                "recipient": recipient,
                "first_message": first_message,
                "file_ids": [],
                "caption": caption,
                "state": state,
            },
        )
        for file_id in deduped:
            if file_id not in group["file_ids"]:
                group["file_ids"].append(file_id)

        if key in MEDIA_GROUP_TASKS:
            return

        task = asyncio.create_task(_flush_media_group_after_delay(key))
        MEDIA_GROUP_TASKS[key] = task


async def _flush_media_group_after_delay(key: tuple[int, int, str]) -> None:
    try:
        await asyncio.sleep(1.0)
    finally:
        async with MEDIA_GROUP_LOCK:
            payload = MEDIA_GROUP_CACHE.pop(key, None)
            MEDIA_GROUP_TASKS.pop(key, None)

        if not payload:
            return

        try:
            first_message: Message = payload["first_message"]
            session: AsyncSession = payload["session"]
            sender: User = payload["sender"]
            recipient: User = payload["recipient"]
            state = payload["state"]

            ok = await send_anonymous_message(
                session=session,
                sender=sender,
                recipient=recipient,
                original_message=first_message,
                media_group_file_ids=payload["file_ids"],
            )

            if ok and state is not None:
                await state.clear()

        except Exception:
            logging.exception("Не удалось выполнить flush для media_group %s", key)


async def send_anonymous_message(
    session: AsyncSession,
    sender: User,
    recipient: User,
    original_message: Message,
    media_group_file_ids: list[str] | None = None,
) -> bool:
    """
    Отправляет анонимное сообщение.
    Поддерживает: текст, одну фотографию, альбомы, видео, кружочки, стикеры.
    """
    text_content = (original_message.text or original_message.caption or "").strip()
    bot_username = (await original_message.bot.get_me()).username or "sluhisosedibot"

    builder = InlineKeyboardBuilder()
    db_msg = DBMessage(sender_id=sender.id, recipient_id=recipient.id, text=text_content)
    session.add(db_msg)
    await session.commit()

    builder.button(
        text="Ответить",
        callback_data=MsgActionCB(action="reply", message_id=db_msg.id, sender_id=sender.id).pack(),
        icon_custom_emoji_id=Emojis.REPLY.custom_id,
    )
    builder.button(
        text="Заблокировать",
        callback_data=MsgActionCB(action="block", message_id=db_msg.id, sender_id=sender.id).pack(),
        icon_custom_emoji_id=Emojis.BLOCK.custom_id,
    )
    builder.button(
        text="Пожаловаться",
        callback_data=MsgActionCB(action="report", message_id=db_msg.id, sender_id=sender.id).pack(),
        icon_custom_emoji_id=Emojis.REPORT.custom_id,
    )

    if recipient.role in ["admin", "owner", "moderator", "vip"]:
        builder.button(
            text="Кто отправил?",
            callback_data=AdminCB(action="reveal", target_id=sender.telegram_id, page=db_msg.id).pack(),
            icon_custom_emoji_id=Emojis.ADMIN.custom_id,
        )
        builder.adjust(1, 2, 1)
    else:
        builder.adjust(1, 2)

    reply_markup = builder.as_markup()
    content_block = f"{text_content}\n\n" if text_content else ""
    message_text = (
        f"{Emojis.MAIL} <b>У тебя новое анонимное сообщение!</b>\n\n"
        f"{content_block}"
        f"{Emojis.REPLY} <i>Свайпни для ответа</i>\n\n"
        f"{Emojis.BOT} <code>@{bot_username}</code>"
    )

    try:
        if original_message.content_type == "text":
            await original_message.bot.send_message(
                chat_id=recipient.telegram_id,
                text=message_text,
                reply_markup=reply_markup,
            )
            return True

        if media_group_file_ids:
            media = []
            for index, file_id in enumerate(_dedupe_file_ids(media_group_file_ids)):
                media.append(
                    InputMediaPhoto(
                        media=file_id,
                        caption=message_text if index == 0 else None,
                        parse_mode="HTML",
                    )
                )
            if media:
                await original_message.bot.send_media_group(chat_id=recipient.telegram_id, media=media)
                return True

        photos = getattr(original_message, "photo", None) or []
        if photos:
            best_photo = photos[-1]
            await original_message.bot.send_photo(
                chat_id=recipient.telegram_id,
                photo=best_photo.file_id,
                caption=message_text,
                parse_mode="HTML",
                reply_markup=reply_markup,
            )
            return True

        await original_message.copy_to(
            chat_id=recipient.telegram_id,
            caption=message_text,
            reply_markup=reply_markup,
        )
        return True

    except Exception:
        logging.exception("Ошибка отправки анонимного сообщения для %s -> %s", sender.id, recipient.id)
        return False