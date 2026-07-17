from bot import order_stub
from bot.models import OrderState


def test_known_order_returns_status():
    order = order_stub.get_order_status("12345")
    assert order is not None
    assert order.order_id == "12345"
    assert order.status == OrderState.SHIPPING
    assert order.estimated_delivery


def test_unknown_order_returns_none():
    assert order_stub.get_order_status("00000-not-real") is None


def test_order_id_is_stripped():
    order = order_stub.get_order_status("  67890  ")
    assert order is not None
    assert order.order_id == "67890"
    assert order.status == OrderState.DELIVERED
