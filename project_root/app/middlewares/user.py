from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery, TelegramObject
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database.models import User
from app.services.crypto import generate_personal_token
from app.texts.templates import Texts
from app.config import config

class UserMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        
        tg_user = data.get("event_from_user")
        if not tg_user or tg_user.is_bot:
            return await handler(event, data)

        session: AsyncSession = data["session"]
        
        # Ищем пользователя в БД
        result = await session.execute(select(User).where(User.telegram_id == tg_user.id))
        db_user = result.scalar_one_or_none()
        
        # Если пользователя нет - регистрируем
        if not db_user:
            # Назначаем owner_id из конфигурации
            role = "owner" if tg_user.id == config.OWNER_ID else "user"
            db_user = User(
                telegram_id=tg_user.id,
                username=tg_user.username,
                role=role,
                personal_token=generate_personal_token()
            )
            session.add(db_user)
            await session.commit()
            await session.refresh(db_user)
            
        # Обновляем юзернейм, если он сменился
        elif db_user.username != tg_user.username:
            db_user.username = tg_user.username
            await session.commit()

        data["db_user"] = db_user

        allow_banned_start = isinstance(event, Message) and bool(
            event.text and event.text.split(maxsplit=1)[0].split("@", maxsplit=1)[0] == "/start"
        )

        if db_user.is_banned and allow_banned_start:
            await event.answer(Texts.BANNED_SCREEN)
            return

        if db_user.is_banned:
            if isinstance(event, Message):
                await event.answer(Texts.ERR_BANNED)
            elif isinstance(event, CallbackQuery):
                await event.answer(Texts.ERR_BANNED, show_alert=True)
            return
        
        return await handler(event, data)