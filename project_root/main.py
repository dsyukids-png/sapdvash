import asyncio
import logging
import sqlite3
from pathlib import Path

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramConflictError
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.storage.redis import RedisStorage
from redis.asyncio import Redis

from app.config import config
from app.database import Base, engine, async_session
from app.middlewares import DbSessionMiddleware, UserMiddleware, ThrottlingMiddleware
from app.handlers.user import user_router
from app.handlers.support import support_router
from app.handlers.admin import admin_router


async def create_storage_and_redis():
    redis_client = None
    storage = MemoryStorage()

    try:
        redis_client = Redis.from_url(config.redis_url, decode_responses=False)
        await redis_client.ping()
        storage = RedisStorage(redis=redis_client)
        return storage, redis_client
    except Exception as exc:
        if redis_client is not None:
            await redis_client.aclose()
        logging.getLogger(__name__).warning(
            "Redis недоступен (%s). Использую MemoryStorage для FSM.",
            exc,
        )
        return storage, None


def ensure_sqlite_schema_compatibility():
    sqlite_path = Path("bot.db")
    if not sqlite_path.exists():
        return

    try:
        conn = sqlite3.connect(sqlite_path)
        try:
            columns = conn.execute("PRAGMA table_info(users)").fetchall()
            existing = {col[1] for col in columns}

            if "support_banned_until" not in existing:
                conn.execute("ALTER TABLE users ADD COLUMN support_banned_until DATETIME")
            if "support_spam_level" not in existing:
                conn.execute("ALTER TABLE users ADD COLUMN support_spam_level INTEGER NOT NULL DEFAULT 0")
            conn.commit()
            logging.getLogger(__name__).info("SQLite схема обновлена для поддержки спам-лимитов.")
        finally:
            conn.close()
    except Exception as exc:
        logging.getLogger(__name__).warning("Не удалось обновить SQLite схему: %s", exc)


async def main():
    # Настройка логирования
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(name)s - %(message)s"
    )
    logger = logging.getLogger(__name__)

    ensure_sqlite_schema_compatibility()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    storage, redis_client = await create_storage_and_redis()

    # Инициализация бота
    bot = Bot(
        token=config.BOT_TOKEN.get_secret_value(),
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    dp = Dispatcher(storage=storage)

    # Регистрация Middlewares (порядок важен!)
    # 1. DbSessionMiddleware дает сессию БД всем хэндлерам
    dp.update.middleware(DbSessionMiddleware(async_session_maker := async_session))

    # 2. UserMiddleware регистрирует пользователя и проверяет баны
    dp.update.middleware(UserMiddleware())

    # 3. ThrottlingMiddleware защищает от спама и флуда через Redis
    if redis_client is not None:
        dp.update.middleware(ThrottlingMiddleware(redis=redis_client))

    # Регистрация роутеров хэндлеров
    dp.include_router(user_router)
    dp.include_router(support_router)
    dp.include_router(admin_router)

    logger.info("Бот успешно запущен и готов к работе!")

    try:
        # Пропускаем старые апдейты и запускаем поллинг
        await bot.delete_webhook(drop_pending_updates=True)
        try:
            await dp.start_polling(bot)
        except TelegramConflictError:
            logger.error("Конфликт polling: другой экземпляр этого бота уже запущен. Завершение работы.")
            return
    finally:
        await bot.session.close()
        if redis_client is not None:
            await redis_client.close()
        await engine.dispose()
        logger.info("Соединения закрыты. Бот остановлен.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Работа бота завершена пользователем.")