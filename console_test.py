"""Консольный тест-харнесс для проверки диалога без Telegram-токена и ключей.

Запуск:
    python console_test.py

Дополнительно:
    python console_test.py --show-tickets   — показать сохранённые тикеты
    python console_test.py --show-stats     — показать статистику взаимодействий

Логика диалога полностью совпадает с той, что использует Telegram-бот
(bot/dialog.py) — отличается только транспорт (ввод/вывод в консоли вместо
Telegram-сообщений). Без PROXYAPI_KEY GigaChat работает в офлайн-режиме и
отвечает напрямую на основе базы знаний.

Тестовые номера заказов для проверки сценария «статус заказа»: 12345, 67890,
11111, 22222, 99999 (любой другой номер — «не найден», как и будет с реальным
несуществующим order_id).
"""
from __future__ import annotations

import asyncio
import sys

# На Windows консоль по умолчанию может быть не в UTF-8 — без этого кириллица
# и эмодзи в диалоге и результатах могут отображаться некорректно.
if hasattr(sys.stdout, "reconfigure") and sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stdin, "reconfigure") and sys.stdin.encoding and sys.stdin.encoding.lower() != "utf-8":
    sys.stdin.reconfigure(encoding="utf-8")

from bot import dialog, stats, ticket_stub
from bot.config import settings
from bot.gigachat_client import get_gigachat_client
from bot.models import DialogSession, Topic


def _print_table(rows: list[dict], columns: list[str]) -> None:
    if not rows:
        print("(пусто)")
        return
    for row in rows:
        print(" | ".join(f"{col}={row.get(col)}" for col in columns))


def show_tickets() -> None:
    rows = ticket_stub.get_all_tickets()
    print(f"Сохранённые тикеты ({len(rows)}):")
    _print_table(rows, ["ticket_id", "contact", "topic", "message", "status", "created_at"])


def show_stats() -> None:
    rows = stats.get_all_interactions()
    print(f"Статистика взаимодействий ({len(rows)}), диалогов: {stats.count_dialogs()}:")
    _print_table(rows, ["chat_id", "topic", "answered_by", "created_at"])


async def run_console() -> None:
    stats.init_db()
    ticket_stub.init_db()

    if settings.gigachat_mock_mode:
        print(
            "[офлайн-режим] PROXYAPI_KEY не задан — GigaChat не вызывается, "
            "ответы формируются из базы знаний напрямую.\n"
        )

    client = get_gigachat_client()
    session = DialogSession(chat_id="console-user")
    print(dialog.start_dialog(session))
    print(
        "(команды: 'каталог', 'статус заказа', 'поддержка', "
        "'выход' — закончить сессию)\n"
    )

    try:
        while True:
            try:
                user_text = input("Вы: ").strip()
            except (EOFError, KeyboardInterrupt):
                break

            if not user_text:
                continue
            if user_text.lower() in ("выход", "exit", "quit"):
                break

            if user_text.lower() == "каталог":
                print(f"Бот: {await dialog.answer_topic_button(session, client, Topic.PRODUCTS)}\n")
                continue

            if user_text.lower() == "поддержка":
                print(f"Бот: {await dialog.request_manager(session)}\n")
                continue

            reply = await dialog.handle_message(session, client, user_text)
            print(f"Бот: {reply}\n")

            if session.state.value == "closed":
                break
    finally:
        await client.aclose()

    show_tickets()
    show_stats()


if __name__ == "__main__":
    if "--show-tickets" in sys.argv:
        show_tickets()
    elif "--show-stats" in sys.argv:
        show_stats()
    else:
        asyncio.run(run_console())
