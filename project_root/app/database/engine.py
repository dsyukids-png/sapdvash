import os

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.config import config


DATABASE_URL = config.database_url
if os.getenv("BOT_USE_SQLITE", "1").lower() in {"1", "true", "yes", "on"} and config.DB_HOST in {"localhost", "127.0.0.1", "::1"}:
    DATABASE_URL = "sqlite+aiosqlite:///./bot.db"

engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
)

async_session = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)