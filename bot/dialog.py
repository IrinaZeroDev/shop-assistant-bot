"""Движок диалога — вся бизнес-логика сценария, не зависящая от транспорта.

Используется и Telegram-обработчиками (handlers.py), и консольным
тест-харнессом (console_test.py), поэтому его можно тестировать и
эксплуатировать без Telegram-токена.

Три сценария: вопросы о товарах/поддержке (через базу знаний), проверка
статуса заказа (через order_stub) и эскалация на менеджера с согласия
клиента или автоматически, если бот не может честно ответить.
"""
from __future__ import annotations

import logging
import time
from typing import List, Optional

from bot import order_stub, stats, ticket_stub
from bot.config import settings
from bot.gigachat_client import BaseGigaChatClient, GigaChatError, GigaChatUnavailableError
from bot.knowledge_base import GREETING_TEXT, KNOWLEDGE_BASE, find_topic, get_answer
from bot.messages import (
    ASK_ORDER_ID,
    CLOSE_KEYWORDS,
    CLOSED_MESSAGE,
    CLOSING_MESSAGE,
    CONSENT_DECLINED,
    CONSENT_PROMPT_SUFFIX,
    CONSENT_UNCLEAR,
    FALLBACK_MESSAGE,
    GREETING_KEYWORDS,
    GREETING_SMALLTALK_REPLY,
    MANAGER_REQUEST_KEYWORDS,
    NEGATIVE_WORDS,
    OFF_TOPIC_MESSAGE,
    ORDER_ID_EMPTY_RETRY,
    ORDER_ID_TOO_LONG_RETRY,
    ORDER_NOT_FOUND_TEMPLATE,
    ORDER_STATUS_KEYWORDS,
    POSITIVE_WORDS,
    SCOPE_KEYWORDS,
    STEP_IN_PROGRESS_RETRY,
    SYSTEM_PROMPT_TEMPLATE,
    THANKS_KEYWORDS,
    THANKS_REPLY,
    TICKET_SUBMITTED_MESSAGE,
)
from bot.models import DialogSession, DialogState, Ticket, TicketStatus, Topic

logger = logging.getLogger(__name__)

MAX_ORDER_ID_LENGTH = 40

# Темы, после которых уместно сразу предложить связь с менеджером — по ним
# обычно нужно реальное действие человека, а не просто справка.
_MANAGER_LEANING_TOPICS = (
    Topic.CANCEL_CHANGE,
    Topic.DAMAGED_ITEM,
    Topic.WARRANTY_RETURN,
    Topic.SUPPORT_CONTACT,
)


def _normalize(text: str) -> str:
    """Приводит пользовательский ввод к нижнему регистру без пробелов по краям."""
    return text.strip().lower()


def _contains_any(text: str, keywords: List[str]) -> bool:
    return any(kw in text for kw in keywords)


def _parse_yes_no(text: str) -> Optional[bool]:
    """Грубый разбор ответа да/нет. Возвращает None, если ответ неоднозначен."""
    normalized = _normalize(text)
    if _contains_any(normalized, NEGATIVE_WORDS):
        return False
    if _contains_any(normalized, POSITIVE_WORDS):
        return True
    return None


def start_dialog(session: DialogSession) -> str:
    """Переводит сессию в рабочее состояние и возвращает приветствие."""
    session.state = DialogState.CHATTING
    return GREETING_TEXT


async def handle_message(
    session: DialogSession,
    client: BaseGigaChatClient,
    user_text: str,
) -> str:
    """Главная точка входа движка диалога — обрабатывает одно сообщение клиента."""
    if session.state == DialogState.GREETING:
        start_dialog(session)

    normalized = _normalize(user_text)

    if session.state == DialogState.CLOSED:
        return CLOSED_MESSAGE

    if _contains_any(normalized, CLOSE_KEYWORDS) or normalized in ("/end",):
        session.state = DialogState.CLOSED
        return CLOSING_MESSAGE

    if session.state == DialogState.AWAITING_CONSENT:
        return await _handle_consent_answer(session, user_text)

    if session.state == DialogState.AWAITING_ORDER_ID:
        return await _handle_order_id(session, user_text)

    # Обычный вопрос в состоянии CHATTING
    session.user_message_count += 1
    return await _handle_question(session, client, user_text)


async def _handle_consent_answer(session: DialogSession, user_text: str) -> str:
    answer = _parse_yes_no(user_text)
    if answer is True:
        return await _submit_ticket_from_session(session, status=TicketStatus.NEW)
    if answer is False:
        session.consent_given = False
        session.state = DialogState.CHATTING
        session.pending_ticket_message = None
        return CONSENT_DECLINED
    return CONSENT_UNCLEAR


async def _handle_order_id(session: DialogSession, user_text: str) -> str:
    order_id = user_text.strip()
    if not order_id:
        return ORDER_ID_EMPTY_RETRY
    if len(order_id) > MAX_ORDER_ID_LENGTH:
        return ORDER_ID_TOO_LONG_RETRY

    start = time.monotonic()
    order = order_stub.get_order_status(order_id)
    session.state = DialogState.CHATTING

    if order is not None:
        reply = (
            f"Заказ №{order.order_id}: статус «{order.status.value}», "
            f"ожидаемая дата доставки — {order.estimated_delivery}."
        )
        stats.record_interaction(
            chat_id=session.chat_id,
            topic=Topic.ORDER_STATUS.value,
            question=f"заказ №{order_id}",
            answered_by="order_status",
            response_time_ms=int((time.monotonic() - start) * 1000),
        )
        return reply

    reply = ORDER_NOT_FOUND_TEMPLATE.format(order_id=order_id)
    ticket = Ticket(
        contact=session.chat_id,
        topic=Topic.ORDER_STATUS.value,
        message=f"Не найден заказ №{order_id}",
        status=TicketStatus.NEEDS_MANAGER,
    )
    await ticket_stub.submit_ticket(ticket)
    stats.record_interaction(
        chat_id=session.chat_id,
        topic=Topic.ORDER_STATUS.value,
        question=f"заказ №{order_id}",
        answered_by="manager",
        response_time_ms=int((time.monotonic() - start) * 1000),
    )
    return reply


async def _handle_question(
    session: DialogSession,
    client: BaseGigaChatClient,
    user_text: str,
) -> str:
    normalized = _normalize(user_text)

    if _contains_any(normalized, GREETING_KEYWORDS) and len(normalized) < 40:
        return GREETING_SMALLTALK_REPLY

    if _contains_any(normalized, THANKS_KEYWORDS) and len(normalized) < 40:
        return THANKS_REPLY

    if _contains_any(normalized, ORDER_STATUS_KEYWORDS):
        session.state = DialogState.AWAITING_ORDER_ID
        return ASK_ORDER_ID

    # Классификация по базе знаний — приоритетнее эвристики "просит менеджера",
    # иначе вопросы вроде "как связаться с поддержкой" (тема SUPPORT_CONTACT)
    # будут перехватываться раньше, чем до них дойдёт поиск по базе знаний.
    topic = find_topic(user_text)
    start = time.monotonic()

    if topic is None:
        if _contains_any(normalized, MANAGER_REQUEST_KEYWORDS):
            session.pending_ticket_message = user_text
            return await _submit_ticket_from_session(session, status=TicketStatus.NEW)

        if _contains_any(normalized, SCOPE_KEYWORDS) or "?" in user_text:
            reply = await _escalate_to_manager(session, user_text, topic=None)
            stats.record_interaction(
                chat_id=session.chat_id,
                topic=Topic.OTHER.value,
                question=user_text,
                answered_by="manager",
                response_time_ms=int((time.monotonic() - start) * 1000),
            )
            return reply

        stats.record_interaction(
            chat_id=session.chat_id,
            topic=None,
            question=user_text,
            answered_by="offtopic",
        )
        return OFF_TOPIC_MESSAGE

    return await _answer_known_topic(session, client, topic, user_text, start)


async def _answer_known_topic(
    session: DialogSession,
    client: BaseGigaChatClient,
    topic: Topic,
    log_question: str,
    start: float,
) -> str:
    session.last_topic = topic
    kb_answer = get_answer(topic)
    reply = await _answer_with_context(client, log_question, kb_answer)
    answered_by = "kb_llm"

    if reply is None:
        reply = await _escalate_to_manager(session, log_question, topic=topic)
        answered_by = "manager"

    stats.record_interaction(
        chat_id=session.chat_id,
        topic=topic.value,
        question=log_question,
        answered_by=answered_by,
        response_time_ms=int((time.monotonic() - start) * 1000),
    )

    if answered_by == "kb_llm":
        session.pending_ticket_message = log_question
        reply = _maybe_prompt_consent(session, reply, topic)

    return reply


async def _answer_with_context(
    client: BaseGigaChatClient, user_text: str, kb_answer: Optional[str]
) -> Optional[str]:
    """Вызывает GigaChat с контекстом из базы знаний; None — сигнал эскалации."""
    system_prompt = SYSTEM_PROMPT_TEMPLATE.format(context=kb_answer or "")
    try:
        return await client.generate(system_prompt, user_text)
    except GigaChatUnavailableError:
        logger.error("GigaChat недоступен после retry — эскалация на менеджера")
        return None
    except GigaChatError:
        logger.error("Ошибка GigaChat (не retry) — эскалация на менеджера")
        return None


async def _escalate_to_manager(
    session: DialogSession, user_text: str, topic: Optional[Topic]
) -> str:
    ticket = Ticket(
        contact=session.chat_id,
        topic=(topic.value if topic else Topic.OTHER.value),
        message=user_text,
        status=TicketStatus.NEEDS_MANAGER,
    )
    await ticket_stub.submit_ticket(ticket)
    return FALLBACK_MESSAGE


async def _submit_ticket_from_session(session: DialogSession, status: TicketStatus) -> str:
    message = session.pending_ticket_message or "Клиент попросил связаться с менеджером"
    topic = session.last_topic.value if session.last_topic else Topic.OTHER.value
    ticket = Ticket(contact=session.chat_id, topic=topic, message=message, status=status)
    await ticket_stub.submit_ticket(ticket)

    session.consent_given = True
    session.state = DialogState.CHATTING
    session.pending_ticket_message = None

    return TICKET_SUBMITTED_MESSAGE


def _maybe_prompt_consent(session: DialogSession, reply: str, topic: Topic) -> str:
    if session.consent_given is True:
        return reply

    manager_leaning = topic in _MANAGER_LEANING_TOPICS
    threshold_reached = session.user_message_count >= settings.consent_prompt_after_messages

    if session.consent_given is None and (manager_leaning or threshold_reached):
        session.state = DialogState.AWAITING_CONSENT
        return reply + CONSENT_PROMPT_SUFFIX

    return reply


async def request_manager(session: DialogSession) -> str:
    """Запускает передачу менеджеру в обход эвристик — по явному действию
    клиента (кнопка «Связаться с поддержкой»). Само действие уже есть согласие."""
    if session.state == DialogState.GREETING:
        start_dialog(session)
    if session.state not in (DialogState.CHATTING, DialogState.AWAITING_CONSENT):
        return STEP_IN_PROGRESS_RETRY

    session.pending_ticket_message = session.pending_ticket_message or "Клиент запросил связь с менеджером"
    return await _submit_ticket_from_session(session, status=TicketStatus.NEW)


async def start_order_lookup(session: DialogSession) -> str:
    """Запускает проверку статуса заказа по кнопке, в обход эвристик."""
    if session.state == DialogState.GREETING:
        start_dialog(session)
    if session.state != DialogState.CHATTING:
        return STEP_IN_PROGRESS_RETRY
    session.state = DialogState.AWAITING_ORDER_ID
    return ASK_ORDER_ID


async def answer_topic_button(
    session: DialogSession,
    client: BaseGigaChatClient,
    topic: Topic,
) -> str:
    """Ответ на выбор темы кнопкой (например, «Каталог товаров»).

    Использует тот же движок, что и обычный вопрос текстом.
    """
    if session.state == DialogState.GREETING:
        start_dialog(session)
    if session.state != DialogState.CHATTING:
        return STEP_IN_PROGRESS_RETRY

    session.user_message_count += 1
    start = time.monotonic()
    title = KNOWLEDGE_BASE[topic].title
    return await _answer_known_topic(session, client, topic, f"[кнопка] {title}", start)
