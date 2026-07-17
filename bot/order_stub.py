"""Тестовая заглушка REST API проверки статуса заказа (GET /orders/{order_id}).

Реальной системы заказов у заказчика нет и не будет (подтверждено явно) —
это постоянная заглушка с тестовыми order_id, а не временный мок для
последующей замены на боевой эндпоинт.
"""
from __future__ import annotations

from typing import Optional

from bot.models import OrderState, OrderStatus

# ЗАГЛУШКА — тестовые заказы для проверки сценария (order_id -> данные)
_TEST_ORDERS: dict[str, dict] = {
    "12345": {
        "status": OrderState.SHIPPING,
        "estimated_delivery": "2026-07-20",
    },
    "67890": {
        "status": OrderState.DELIVERED,
        "estimated_delivery": "2026-07-15",
    },
    "11111": {
        "status": OrderState.PROCESSING,
        "estimated_delivery": "2026-07-24",
    },
    "22222": {
        "status": OrderState.ASSEMBLED,
        "estimated_delivery": "2026-07-19",
    },
    "99999": {
        "status": OrderState.CANCELLED,
        "estimated_delivery": "—",
    },
}


def get_order_status(order_id: str) -> Optional[OrderStatus]:
    """Имитирует GET /orders/{order_id}. None — заказ не найден в заглушке.

    Для проверки сценария используйте тестовые номера: 12345, 67890, 11111,
    22222, 99999 — остальные считаются не найденными (как и будет с реальным
    order_id, которого нет в системе).
    """
    order_id = order_id.strip()
    data = _TEST_ORDERS.get(order_id)
    if data is None:
        return None
    return OrderStatus(
        order_id=order_id,
        status=data["status"],
        estimated_delivery=data["estimated_delivery"],
    )
