from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from app.texts.emojis import Emojis
from app.keyboards.callbacks import MenuCB


def make_button(text: str, callback_data: str | None = None, url: str | None = None, icon_id: str | None = None) -> InlineKeyboardButton:
    return InlineKeyboardButton(
        text=text,
        callback_data=callback_data,
        url=url,
        icon_custom_emoji_id=icon_id,
    )


def get_main_menu_kb() -> InlineKeyboardMarkup:
    """Главное меню бота."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                make_button(
                    text="Моя ссылка",
                    callback_data=MenuCB(action="link").pack(),
                    icon_id=Emojis.LINK.custom_id,
                ),
                make_button(
                    text="Мои сообщения",
                    callback_data=MenuCB(action="inbox").pack(),
                    icon_id=Emojis.INBOX.custom_id,
                ),
            ],
            [
                make_button(
                    text="Настройки",
                    callback_data=MenuCB(action="settings").pack(),
                    icon_id=Emojis.SETTINGS.custom_id,
                ),
                make_button(
                    text="Поддержка",
                    callback_data=MenuCB(action="support").pack(),
                    icon_id=Emojis.SUPPORT.custom_id,
                ),
            ],
            [
                make_button(
                    text="Помощь",
                    callback_data=MenuCB(action="help").pack(),
                    icon_id=Emojis.HELP.custom_id,
                )
            ],
        ]
    )


def get_back_kb(target_menu: str = "main") -> InlineKeyboardMarkup:
    """Универсальная кнопка Назад."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                make_button(
                    text="Назад",
                    callback_data=MenuCB(action=target_menu).pack(),
                    icon_id=Emojis.BACK.custom_id,
                )
            ]
        ]
    )


