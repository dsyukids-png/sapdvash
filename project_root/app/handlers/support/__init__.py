from aiogram import Router
from .tickets import router as tickets_router

support_router = Router()
support_router.include_router(tickets_router)