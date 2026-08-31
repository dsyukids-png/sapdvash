from aiogram import Router
from .basic import router as basic_router
from .menu import router as menu_router
from .messaging import router as messaging_router
from .actions import router as actions_router

# Создаем общий роутер для всех действий пользователя
user_router = Router()
user_router.include_router(basic_router)
user_router.include_router(menu_router)
user_router.include_router(messaging_router)
user_router.include_router(actions_router)