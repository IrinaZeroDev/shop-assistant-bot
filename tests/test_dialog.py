import pytest

from bot import dialog
from bot.config import settings
from bot.gigachat_client import MockGigaChatClient
from bot.models import DialogState, Topic


@pytest.fixture(autouse=True)
def isolated_dbs(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "stats_db_path", str(tmp_path / "stats.sqlite3"))
    monkeypatch.setattr(settings, "tickets_db_path", str(tmp_path / "tickets.sqlite3"))
    yield


@pytest.fixture
def client():
    return MockGigaChatClient()


def _session():
    from bot.models import DialogSession

    return DialogSession(chat_id="test-chat")


def test_start_dialog_returns_greeting():
    session = _session()
    greeting = dialog.start_dialog(session)
    assert session.state == DialogState.CHATTING
    assert "привет" in greeting.lower()


@pytest.mark.asyncio
async def test_known_topic_answers_from_kb(client):
    session = _session()
    dialog.start_dialog(session)
    reply = await dialog.handle_message(session, client, "Какие способы оплаты доступны?")
    assert "оплат" in reply.lower() or "картой" in reply.lower()


@pytest.mark.asyncio
async def test_offtopic_question_gets_scope_redirect(client):
    session = _session()
    dialog.start_dialog(session)
    reply = await dialog.handle_message(session, client, "какая сегодня погода")
    assert reply == dialog.OFF_TOPIC_MESSAGE


@pytest.mark.asyncio
async def test_unmatched_but_relevant_question_escalates_to_manager(client):
    session = _session()
    dialog.start_dialog(session)
    reply = await dialog.handle_message(session, client, "У вас есть кэшбэк за заказ?")
    assert "менеджер" in reply.lower()


@pytest.mark.asyncio
async def test_order_status_found_flow(client):
    session = _session()
    dialog.start_dialog(session)

    reply = await dialog.handle_message(session, client, "статус заказа")
    assert session.state == DialogState.AWAITING_ORDER_ID
    assert "номер" in reply.lower()

    reply = await dialog.handle_message(session, client, "12345")
    assert session.state == DialogState.CHATTING
    assert "12345" in reply
    assert "доставке" in reply.lower()


@pytest.mark.asyncio
async def test_order_status_not_found_creates_ticket(client):
    session = _session()
    dialog.start_dialog(session)
    await dialog.handle_message(session, client, "где мой заказ")
    reply = await dialog.handle_message(session, client, "00000")

    assert "менеджер" in reply.lower()
    assert session.state == DialogState.CHATTING

    from bot import ticket_stub

    tickets = ticket_stub.get_all_tickets()
    assert len(tickets) == 1
    assert tickets[0]["status"] == "needs_manager"
    assert "00000" in tickets[0]["message"]


@pytest.mark.asyncio
async def test_explicit_manager_request_creates_ticket_immediately(client):
    session = _session()
    dialog.start_dialog(session)
    reply = await dialog.handle_message(session, client, "Хочу поговорить с менеджером")

    assert "менеджер" in reply.lower()
    assert session.state == DialogState.CHATTING

    from bot import ticket_stub

    tickets = ticket_stub.get_all_tickets()
    assert len(tickets) == 1
    assert tickets[0]["status"] == "new"


@pytest.mark.asyncio
async def test_manager_leaning_topic_prompts_consent(client):
    session = _session()
    dialog.start_dialog(session)
    reply = await dialog.handle_message(session, client, "Товар пришёл повреждённым")
    assert session.state == DialogState.AWAITING_CONSENT
    assert "менеджер" in reply.lower()


@pytest.mark.asyncio
async def test_consent_yes_creates_ticket(client):
    session = _session()
    dialog.start_dialog(session)
    await dialog.handle_message(session, client, "Товар пришёл повреждённым")
    reply = await dialog.handle_message(session, client, "да")

    assert session.state == DialogState.CHATTING
    from bot import ticket_stub

    tickets = ticket_stub.get_all_tickets()
    assert len(tickets) == 1
    assert tickets[0]["status"] == "new"
    assert tickets[0]["topic"] == Topic.DAMAGED_ITEM.value


@pytest.mark.asyncio
async def test_consent_no_declines(client):
    session = _session()
    dialog.start_dialog(session)
    await dialog.handle_message(session, client, "Товар пришёл повреждённым")
    reply = await dialog.handle_message(session, client, "нет")

    assert session.state == DialogState.CHATTING
    assert "хорошо" in reply.lower()

    from bot import ticket_stub

    assert ticket_stub.get_all_tickets() == []


@pytest.mark.asyncio
async def test_close_flow(client):
    session = _session()
    dialog.start_dialog(session)
    reply = await dialog.handle_message(session, client, "спасибо, всё, пока")
    assert session.state == DialogState.CLOSED
    assert reply == dialog.CLOSING_MESSAGE

    reply = await dialog.handle_message(session, client, "ещё вопрос")
    assert reply == dialog.CLOSED_MESSAGE


@pytest.mark.asyncio
async def test_catalog_button(client):
    session = _session()
    dialog.start_dialog(session)
    reply = await dialog.answer_topic_button(session, client, Topic.PRODUCTS)
    assert "₽" in reply
    assert session.last_topic == Topic.PRODUCTS


@pytest.mark.asyncio
async def test_order_lookup_button(client):
    session = _session()
    dialog.start_dialog(session)
    reply = await dialog.start_order_lookup(session)
    assert session.state == DialogState.AWAITING_ORDER_ID
    assert "номер" in reply.lower()


@pytest.mark.asyncio
async def test_request_manager_button(client):
    session = _session()
    dialog.start_dialog(session)
    reply = await dialog.request_manager(session)
    assert "менеджер" in reply.lower()

    from bot import ticket_stub

    assert len(ticket_stub.get_all_tickets()) == 1


@pytest.mark.asyncio
async def test_button_blocked_during_order_id_collection(client):
    session = _session()
    dialog.start_dialog(session)
    await dialog.start_order_lookup(session)

    reply = await dialog.answer_topic_button(session, client, Topic.PRODUCTS)
    assert "шаг" in reply.lower()
    assert session.state == DialogState.AWAITING_ORDER_ID
