import pytest

from bot import ticket_stub
from bot.config import settings
from bot.models import Ticket, TicketStatus


@pytest.fixture(autouse=True)
def isolated_tickets_db(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "tickets_db_path", str(tmp_path / "tickets.sqlite3"))
    yield


@pytest.mark.asyncio
async def test_submit_ticket_saves_locally():
    ticket = Ticket(contact="123456", topic="товары", message="Есть ли скидки?")
    result = await ticket_stub.submit_ticket(ticket)
    assert result.ticket_id == ticket.ticket_id

    rows = ticket_stub.get_all_tickets()
    assert len(rows) == 1
    assert rows[0]["contact"] == "123456"
    assert rows[0]["status"] == "new"


@pytest.mark.asyncio
async def test_submit_ticket_needs_manager_status():
    ticket = Ticket(
        contact="654321",
        topic="статус_заказа",
        message="Не найден заказ №00000",
        status=TicketStatus.NEEDS_MANAGER,
    )
    await ticket_stub.submit_ticket(ticket)

    rows = ticket_stub.get_all_tickets()
    assert rows[0]["status"] == "needs_manager"


def test_empty_contact_rejected():
    with pytest.raises(ValueError):
        Ticket(contact="   ", topic="товары", message="вопрос")


def test_empty_message_rejected():
    with pytest.raises(ValueError):
        Ticket(contact="123", topic="товары", message="")
