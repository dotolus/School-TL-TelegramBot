import types
from datetime import date
from unittest.mock import AsyncMock, Mock

import pytest

from bot.claude_assistant import ClassificationResult, classify_message


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
