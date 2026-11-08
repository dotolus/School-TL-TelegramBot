import types
from datetime import date
from unittest.mock import AsyncMock, Mock

import pytest

from bot.claude_assistant import ClassificationError, ClassificationResult, answer_query, classify_message


def make_fake_client(tool_name, tool_input):
    client = Mock()
    client.messages.create = AsyncMock(
        return_value=types.SimpleNamespace(
            content=[types.SimpleNamespace(type="tool_use", name=tool_name, input=tool_input)]
        )
    )
    return client


@pytest.mark.asyncio
async def test_classify_message_returns_query_for_a_question():
    client = make_fake_client(tool_name="query_timeline", tool_input={})
    result = await classify_message(client, "claude-sonnet-5-5", "מה יש השבוע?", date(2026, 11, 8))
    assert result == ClassificationResult(kind="query")


@pytest.mark.asyncio
async def test_classify_message_returns_propose_new_item_with_extracted_fields():
    extracted = {
        "type": "test",
        "m": 11,
        "y": 2026,
        "title": "מבחן במתמטיקה",
        "short": "מבחן במתמטיקה - יום שני, 16.11",
        "full": "מבחן במתמטיקה, חומר: פרקים 1-3",
    }
    client = make_fake_client(tool_name="propose_new_item", tool_input=extracted)
    result = await classify_message(
        client, "claude-sonnet-5-5", "תוסיף מבחן במתמטיקה ביום שני הקרוב", date(2026, 11, 8)
    )
    assert result == ClassificationResult(kind="propose_new_item", item=extracted)


@pytest.mark.asyncio
async def test_classify_message_returns_decline_edit_for_an_edit_request():
    client = make_fake_client(tool_name="decline_edit_request", tool_input={})
    result = await classify_message(client, "claude-sonnet-5-5", "תזיז את המבחן לדצמבר", date(2026, 11, 8))
    assert result == ClassificationResult(kind="decline_edit")


@pytest.mark.asyncio
async def test_classify_message_raises_classification_error_when_no_tool_use_returned():
    client = Mock()
    client.messages.create = AsyncMock(
        return_value=types.SimpleNamespace(content=[types.SimpleNamespace(type="text", text="oops")])
    )
    with pytest.raises(ClassificationError):
        await classify_message(client, "claude-sonnet-5-5", "מה יש השבוע?", date(2026, 11, 8))


@pytest.mark.asyncio
async def test_classify_message_raises_classification_error_when_propose_new_item_missing_a_required_field():
    incomplete = {"type": "test", "m": 11, "y": 2026, "title": "מבחן"}  # missing short/full
    client = make_fake_client(tool_name="propose_new_item", tool_input=incomplete)
    with pytest.raises(ClassificationError):
        await classify_message(client, "claude-sonnet-5-5", "תוסיף מבחן", date(2026, 11, 8))


def make_fake_text_client(text):
    client = Mock()
    client.messages.create = AsyncMock(
        return_value=types.SimpleNamespace(content=[types.SimpleNamespace(type="text", text=text)])
    )
    return client


@pytest.mark.asyncio
async def test_answer_query_returns_claude_text_response():
    client = make_fake_text_client("יש מבחן במתמטיקה ביום שני.")
    answer = await answer_query(
        client,
        "claude-sonnet-5-5",
        "מה יש השבוע?",
        [{"title": "מבחן במתמטיקה", "short": "יום שני, 16.11"}],
        date(2026, 11, 8),
    )
    assert answer == "יש מבחן במתמטיקה ביום שני."


@pytest.mark.asyncio
async def test_answer_query_handles_empty_timeline():
    client = make_fake_text_client("אין כרגע פריטים בציר הזמן.")
    answer = await answer_query(client, "claude-sonnet-5-5", "מה יש השבוע?", [], date(2026, 11, 8))
    assert answer == "אין כרגע פריטים בציר הזמן."
    call_kwargs = client.messages.create.call_args.kwargs
    assert "[]" in call_kwargs["messages"][0]["content"]  # empty list was actually passed through, not skipped
