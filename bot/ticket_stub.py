"""Тестовая заглушка REST API для обращений/тикетов поддержки (POST /tickets).

Реальной системы приёма заявок у заказчика нет и не будет (подтверждено
явно) — тикеты сохраняются только локально в SQLite. Структура тикета
совместима со схемой из спецификации и готова к замене на реальный
эндпоинт, если он появится.
"""
from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

from bot.config import settings
from bot.models import Ticket

logger = logging.getLogger(__name__)


def _connect() -> sqlite3.Connection:
    Path(settings.tickets_db_path).parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(settings.tickets_db_path)


def init_db() -> None:
    """Создаёт таблицу tickets, если она ещё не существует. Идемпотентно."""
    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS tickets (
                ticket_id TEXT PRIMARY KEY,
                contact TEXT NOT NULL,
                topic TEXT NOT NULL,
                message TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )


async def submit_ticket(ticket: Ticket) -> Ticket:
    """Сохраняет тикет локально (единственное хранилище — см. модуль-докстринг)."""
    init_db()
    with _connect() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO tickets
                (ticket_id, contact, topic, message, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                ticket.ticket_id,
                ticket.contact,
                ticket.topic,
                ticket.message,
                ticket.status.value,
                ticket.created_at,
            ),
        )
    logger.info(
        "[TICKET STUB] тикет сохранён: ticket_id=%s topic=%s status=%s",
        ticket.ticket_id,
        ticket.topic,
        ticket.status.value,
    )
    return ticket


def get_all_tickets() -> list[dict]:
    """Возвращает все сохранённые тикеты (для консольного теста и отладки)."""
    init_db()
    with _connect() as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT * FROM tickets ORDER BY created_at DESC").fetchall()
        return [dict(row) for row in rows]
