from aiogram.filters.callback_data import CallbackData

# Навигация по главному меню
class MenuCB(CallbackData, prefix="menu"):
    action: str

# Действия с анонимными сообщениями
class MsgActionCB(CallbackData, prefix="msg"):
    action: str        # reply, block, report
    message_id: int    # ID сообщения в нашей БД
    sender_id: int     # ID отправителя в нашей БД (НЕ Telegram ID)

# Действия в админ-панели
class AdminCB(CallbackData, prefix="adm"):
    action: str
    target_id: int = 0
    page: int = 0

# Действия с тикетами поддержки
class SupportCB(CallbackData, prefix="sup"):
    action: str
    ticket_id: int