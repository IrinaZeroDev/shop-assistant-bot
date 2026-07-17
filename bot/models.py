"""Pydantic-модели: тикет поддержки, статус заказа, состояние диалога."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator

MAX_MESSAGE_LENGTH = 2000


class Topic(str, Enum):
    PRODUCTS = "товары"
    ORDER_STATUS = "статус_заказа"
    DELIVERY = "доставка"
    CANCEL_CHANGE = "отмена_изменение"
    DAMAGED_ITEM = "брак"
    WARRANTY_RETURN = "гарантия_возврат"
    SUPPORT_CONTACT = "поддержка"
    PAYMENT = "оплата"
    OTHER = "другое"


class TicketStatus(str, Enum):
    NEW = "new"
    NEEDS_MANAGER = "needs_manager"


class Ticket(BaseModel):
    """Структура обращения — совместима со схемой из спецификации заказчика.

    contact — telegram_id клиента; собирается и сохраняется только после
    явного согласия (или при автоматической эскалации, где сам факт
    telegram-диалога уже делает chat_id доступным контактом).
    """

    ticket_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    contact: str = Field(min_length=1, max_length=200)
    topic: str
    message: str = Field(min_length=1, max_length=MAX_MESSAGE_LENGTH)
    status: TicketStatus = TicketStatus.NEW
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    @field_validator("contact", "message", mode="before")
    @classmethod
    def _strip_and_require_nonempty(cls, value: str) -> str:
        stripped = value.strip() if isinstance(value, str) else value
        if not stripped:
            raise ValueError("значение не может быть пустым")
        return stripped


class OrderState(str, Enum):
    PROCESSING = "в обработке"
    ASSEMBLED = "собран"
    SHIPPING = "в доставке"
    DELIVERED = "доставлен"
    CANCELLED = "отменён"


class OrderStatus(BaseModel):
    """Структура заглушки статуса заказа — совместима со схемой из спецификации."""

    order_id: str
    status: OrderState
    estimated_delivery: str
    last_updated: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class DialogState(str, Enum):
    GREETING = "greeting"
    CHATTING = "chatting"
    AWAITING_CONSENT = "awaiting_consent"
    AWAITING_ORDER_ID = "awaiting_order_id"
    CLOSED = "closed"


class DialogSession(BaseModel):
    """Состояние одного диалога. Не зависит от транспорта (Telegram/консоль)."""

    chat_id: str
    state: DialogState = DialogState.GREETING
    user_message_count: int = 0
    last_topic: Optional[Topic] = None
    consent_given: Optional[bool] = None
    pending_ticket_message: Optional[str] = None
    started_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
