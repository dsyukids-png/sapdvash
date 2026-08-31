import time
from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery, TelegramObject
from redis.asyncio import Redis

from app.config import config
from app.database.models import User

class ThrottlingMiddleware(BaseMiddleware):
    def __init__(self, redis: Redis):
        super().__init__()
        self.redis = redis

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        tg_user = data.get("event_from_user")
        db_user: User = data.get("db_user")
        
        if not tg_user or not db_user:
            return await handler(event, data)

        # Админы и владельцы в вайтлисте — для них нет лимитов
        if db_user.role in ["admin", "owner", "moderator"]:
            return await handler(event, data)

        user_id = tg_user.id
        current_time = time.time()
        
        # Ключи для Redis
        cooldown_key = f"antispam:cooldown:{user_id}"
        flood_key = f"antispam:flood:{user_id}"

        # 1. Проверка кулдауна (интервал между сообщениями)
        last_time = await self.redis.get(cooldown_key)
        if last_time:
            if current_time - float(last_time) < config.RATE_LIMIT:
                if isinstance(event, Message):
                    await event.answer("⚠️ Не отправляй сообщения так часто! Подожди немного.")
                elif isinstance(event, CallbackQuery):
                    await event.answer("⚠️ Слишком быстро!", show_alert=True)
                return
        
        await self.redis.set(cooldown_key, current_time, ex=5)

        # 2. Проверка количества сообщений в минуту (Flood limit)
        message_count = await self.redis.get(flood_key)
        if message_count and int(message_count) >= config.MAX_MESSAGES_PER_MINUTE:
            if isinstance(event, Message):
                await event.answer("🚫 Превышен лимит сообщений. Вы заблокированы на минуту за спам.")
            return

        # Инкрементируем счетчик сообщений с TTL в 60 секунд
        async with self.redis.pipeline(transaction=True) as pipe:
            pipe.incr(flood_key)
            pipe.expire(flood_key, 60)
            await pipe.execute()

        return await handler(event, data)