"""Обработчики Telegram-сообщений (aiogram) — тонкий транспортный слой.

Вся бизнес-логика вынесена в dialog.py, здесь только маппинг Telegram-апдейтов
на вызовы движка диалога, разметка кнопок и хранение сессий в памяти процесса.
"""
from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.types import KeyboardButton, Message, ReplyKeyboardMarkup

from bot import dialog
from bot.gigachat_client import BaseGigaChatClient
from bot.models import DialogSession, Topic

logger = logging.getLogger(__name__)

router = Router()

CATALOG_BUTTON_TEXT = "🛍 Каталог товаров"
ORDER_BUTTON_TEXT = "📦 Статус заказа"
SUPPORT_BUTTON_TEXT = "💬 Связаться с поддержкой"

# Сессии в памяти процесса — для MVP этого достаточно, при рестарте бота
# диалоги начинаются заново (статистика и тикеты сохраняются отдельно в БД).
_sessions: dict[str, DialogSession] = {}


def _get_session(chat_id: str) -> DialogSession:
    if chat_id not in _sessions:
        _sessions[chat_id] = DialogSession(chat_id=chat_id)
    return _sessions[chat_id]


def _main_menu_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=CATALOG_BUTTON_TEXT), KeyboardButton(text=ORDER_BUTTON_TEXT)],
            [KeyboardButton(text=SUPPORT_BUTTON_TEXT)],
        ],
        resize_keyboard=True,
    )


def build_router(client: BaseGigaChatClient) -> Router:
    """Регистрирует все Telegram-обработчики на общем клиенте GigaChat."""

    @router.message(CommandStart())
    async def on_start(message: Message) -> None:
        chat_id = str(message.chat.id)
        session = DialogSession(chat_id=chat_id)
        _sessions[chat_id] = session
        greeting = dialog.start_dialog(session)
        await message.answer(greeting, reply_markup=_main_menu_keyboard())

    @router.message(F.text == CATALOG_BUTTON_TEXT)
    async def on_catalog_button(message: Message) -> None:
        chat_id = str(message.chat.id)
        session = _get_session(chat_id)
        try:
            reply = await dialog.answer_topic_button(session, client, Topic.PRODUCTS)
        except Exception:
            logger.exception("Ошибка при показе каталога chat_id=%s", chat_id)
            reply = "Не получилось показать каталог, попробуйте ещё раз чуть позже."
        await message.answer(reply)

    @router.message(F.text == ORDER_BUTTON_TEXT)
    async def on_order_button(message: Message) -> None:
        chat_id = str(message.chat.id)
        session = _get_session(chat_id)
        try:
            reply = await dialog.start_order_lookup(session)
        except Exception:
            logger.exception("Ошибка при запуске проверки заказа chat_id=%s", chat_id)
            reply = "Не получилось начать проверку заказа, попробуйте ещё раз чуть позже."
        await message.answer(reply)

    @router.message(F.text == SUPPORT_BUTTON_TEXT)
    async def on_support_button(message: Message) -> None:
        chat_id = str(message.chat.id)
        session = _get_session(chat_id)
        try:
            reply = await dialog.request_manager(session)
        except Exception:
            logger.exception("Ошибка при связи с менеджером chat_id=%s", chat_id)
            reply = "Не получилось передать вопрос менеджеру, попробуйте ещё раз чуть позже."
        await message.answer(reply)

    @router.message()
    async def on_message(message: Message) -> None:
        chat_id = str(message.chat.id)
        session = _get_session(chat_id)
        user_text = message.text or ""

        try:
            reply = await dialog.handle_message(session, client, user_text)
        except Exception:
            logger.exception("Необработанная ошибка при обработке сообщения chat_id=%s", chat_id)
            reply = (
                "Произошла техническая неполадка, уже разбираемся. "
                "Попробуйте, пожалуйста, ещё раз чуть позже."
            )

        await message.answer(reply)

    return router
