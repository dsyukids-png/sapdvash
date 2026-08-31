from aiogram.fsm.state import State, StatesGroup

class MessagingState(StatesGroup):
    waiting_for_anonymous_msg = State()  # Ожидание отправки анонимного сообщения
    waiting_for_reply = State()          # Ожидание ответа на полученное сообщение

class SupportState(StatesGroup):
    waiting_for_ticket_text = State()      # Ожидание текста для нового тикета
    waiting_for_ticket_reply = State()     # Ожидание ответа администратора на тикет
    waiting_for_user_ticket_reply = State()  # Ожидание ответа пользователя в открытый тикет

class AdminState(StatesGroup):
    waiting_for_user_id = State()        # Ожидание Telegram ID для управления доступом