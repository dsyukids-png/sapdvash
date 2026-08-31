import os
from enum import Enum
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import SecretStr


class Role(str, Enum):
    USER = "user"
    VIP = "vip"
    MODERATOR = "moderator"
    ADMIN = "admin"
    OWNER = "owner"


class Settings(BaseSettings):
    # Telegram Bot
    BOT_TOKEN: SecretStr
    BOT_USERNAME: str
    OWNER_ID: int

    # Database (PostgreSQL)
    DB_HOST: str
    DB_PORT: int
    DB_USER: str
    DB_PASS: str
    DB_NAME: str

    # Redis
    REDIS_HOST: str
    REDIS_PORT: int
    REDIS_DB: int = 0

    # Anti-Spam & Limits
    RATE_LIMIT: float = 0.5
    MAX_MESSAGES_PER_MINUTE: int = 10
    MESSAGE_MAX_LENGTH: int = 1024
    COOLDOWN: int = 5
    BAN_DURATION: int = 86400  # 1 day in seconds

    _base_dir = os.path.dirname(os.path.dirname(__file__))
    _env_path = os.path.join(_base_dir, ".env")
    if not os.path.exists(_env_path):
        _env_path = os.path.join(_base_dir, ".env.example")

    model_config = SettingsConfigDict(
        env_file=_env_path,
        env_file_encoding="utf-8",
        extra="ignore"
    )

    @property
    def database_url(self) -> str:
        """Формирует URL для подключения к PostgreSQL (asyncpg)."""
        return f"postgresql+asyncpg://{self.DB_USER}:{self.DB_PASS}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"

    @property
    def redis_url(self) -> str:
        """Формирует URL для подключения к Redis."""
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"


# Инициализация конфигурации
# При импорте config из этого модуля, он автоматически прочитает .env файл
config = Settings()