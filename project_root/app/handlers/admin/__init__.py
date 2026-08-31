from aiogram import Router
from .panel import router as panel_router

admin_router = Router()
admin_router.include_router(panel_router)