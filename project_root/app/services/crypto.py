import uuid

def generate_personal_token() -> str:
    """Генерирует уникальный 32-значный токен для анонимной ссылки."""
    return uuid.uuid4().hex