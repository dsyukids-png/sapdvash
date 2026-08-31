from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardMarkup
from urllib.parse import urlencode
from app.texts.emojis import Emojis
from app.keyboards.callbacks import MsgActionCB, MenuCB

def build_message_action_kb(message_id: int, sender_db_id: int) -> InlineKeyboardMarkup:
    """Клавиатура для карточки полученного анонимного сообщения."""
    builder = InlineKeyboardBuilder()

    builder.button(
        text="Ответить",
        callback_data=MsgActionCB(action="reply", message_id=message_id, sender_id=sender_db_id).pack(),
    )
    builder.button(
        text="Заблокировать",
        callback_data=MsgActionCB(action="block", message_id=message_id, sender_id=sender_db_id).pack(),
    )
    builder.button(
        text="Пожаловаться",
        callback_data=MsgActionCB(action="report", message_id=message_id, sender_id=sender_db_id).pack(),
    )

    builder.adjust(1, 2)
    return builder.as_markup()

def build_share_link_kb(bot_username: str | None, token: str) -> InlineKeyboardMarkup:
    """Клавиатура для расшаривания личной ссылки."""
    username = (bot_username or "").lstrip("@")
    link = f"https://t.me/{username}?start={token}"
    share_url = "https://t.me/share/url?" + urlencode({
        "url": link,
        "text": f"Напиши мне анонимное сообщение! {Emojis.MAIL.plain()}",
    })

    builder = InlineKeyboardBuilder()
    builder.button(text="Открыть ссылку", url=link, icon_custom_emoji_id=Emojis.LINK.custom_id)
    builder.button(text="Поделиться", url=share_url, icon_custom_emoji_id=Emojis.MAIL.custom_id)
    builder.button(text="Назад", callback_data=MenuCB(action="main").pack(), icon_custom_emoji_id=Emojis.BACK.custom_id)
    builder.adjust(1)

    return builder.as_markup()