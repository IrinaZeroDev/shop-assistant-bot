"""Сбор и хранение статистики диалогов в SQLite.

По требованию заказчика: число диалогов, тип вопроса, время ответа.
Конверсия и регулярные отчёты не нужны — данные доступны для разбора при
необходимости, но не просматриваются регулярно.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


def _connect() -> sqlite3.Connection:
    from bot.config import settings

    Path(settings.stats_db_path).parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(settings.stats_db_path)


def init_db() -> None:
    """Создаёт таблицу interactions, если она ещё не существует. Идемпотентно."""
    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS interactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id TEXT NOT NULL,
                topic TEXT,
                question TEXT,
                answered_by TEXT,
                response_time_ms INTEGER,
                created_at TEXT NOT NULL
            )
            """
        )


def record_interaction(
    chat_id: str,
    topic: Optional[str],
    question: str,
    answered_by: str,
    response_time_ms: Optional[int] = None,
) -> None:
    """Логирует одно взаимодействие.

    answered_by: 'kb_llm' | 'manager' | 'offtopic' | 'ticket' | 'order_status'.
    """
    init_db()
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO interactions
                (chat_id, topic, question, answered_by, response_time_ms, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                chat_id,
                topic,
                question,
                answered_by,
                response_time_ms,
                datetime.now(timezone.utc).isoformat(),
            ),
        )


def get_all_interactions() -> list[dict]:
    """Возвращает всю статистику взаимодействий (для консольного теста и отладки)."""
    init_db()
    with _connect() as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT * FROM interactions ORDER BY created_at DESC").fetchall()
        return [dict(row) for row in rows]


def count_dialogs() -> int:
    """Число уникальных диалогов (по chat_id) — метрика, которую просил заказчик."""
    init_db()
    with _connect() as conn:
        row = conn.execute("SELECT COUNT(DISTINCT chat_id) FROM interactions").fetchone()
        return row[0] if row else 0
