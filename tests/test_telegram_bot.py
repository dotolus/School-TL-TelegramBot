from unittest.mock import AsyncMock, Mock

import pytest

from bot.claude_assistant import ClassificationResult
from bot.config import Config
from bot.pending import PendingProposals
from bot.school_tl_client import SchoolTLError
from bot.telegram_bot import handle_confirmation_callback, handle_text_message


def make_config(allowed_user_ids={111}):
    return Config(
        telegram_bot_token="x",
        anthropic_api_key="x",
        claude_model="x",
        school_tl_base_url="x",
        school="x",
        period="x",
        school_class="x",
        admin_password="x",
        allowed_user_ids=frozenset(allowed_user_ids),
    )


def make_update_and_context(
    user_id=111,
    chat_id=1,
    config=None,
    classify_result=None,
    pending=None,
    callback_data=None,
):
    if config is None:
        config = make_config()
    if pending is None:
        pending = PendingProposals()

    update = Mock()
    update.effective_user.id = user_id
    update.effective_chat.id = chat_id
    update.message.reply_text = AsyncMock()
    update.callback_query.data = callback_data
    update.callback_query.edit_message_text = AsyncMock()

    context = Mock()
    context.bot_data = {
        "config": config,
        "pending": pending,
        "school_tl_client": Mock(
            get_timeline=AsyncMock(return_value=[]),
            create_item=AsyncMock(return_value={"id": "stub"}),
        ),
        "claude_client": Mock(),
        "classify_message": AsyncMock(return_value=classify_result),
        "answer_query": AsyncMock(return_value=""),
    }
    return update, context


@pytest.mark.asyncio
async def test_handle_text_message_rejects_unauthorized_user():
    update, context = make_update_and_context(user_id=999, config=make_config(allowed_user_ids={111}))
    await handle_text_message(update, context)
    update.message.reply_text.assert_awaited_once()
    assert "הרשאה" in update.message.reply_text.call_args.args[0]
    context.bot_data["claude_client"].messages.create.assert_not_called()


@pytest.mark.asyncio
async def test_handle_text_message_replies_with_query_answer():
    update, context = make_update_and_context(user_id=111, classify_result=ClassificationResult(kind="query"))
    context.bot_data["school_tl_client"].get_timeline = AsyncMock(return_value=[])
    context.bot_data["answer_query"] = AsyncMock(return_value="אין פריטים.")
    await handle_text_message(update, context)
    update.message.reply_text.assert_awaited_once_with("אין פריטים.")


@pytest.mark.asyncio
async def test_handle_text_message_stores_pending_and_shows_confirmation_for_new_item():
    item = {"title": "מבחן", "short": "16.11", "full": "x", "type": "test", "m": 11, "y": 2026}
    update, context = make_update_and_context(
        user_id=111, classify_result=ClassificationResult(kind="propose_new_item", item=item)
    )
    await handle_text_message(update, context)
    assert context.bot_data["pending"].pop(update.effective_chat.id) == item
    update.message.reply_text.assert_awaited_once()


@pytest.mark.asyncio
async def test_handle_text_message_declines_edit_requests():
    update, context = make_update_and_context(user_id=111, classify_result=ClassificationResult(kind="decline_edit"))
    await handle_text_message(update, context)
    update.message.reply_text.assert_awaited_once()
    context.bot_data["school_tl_client"].create_item.assert_not_called()


@pytest.mark.asyncio
async def test_handle_text_message_second_proposal_replaces_first():
    pending = PendingProposals()
    pending.set(42, {"title": "first", "short": "x", "full": "x"})
    second_item = {"title": "second", "short": "17.11", "full": "x", "type": "test", "m": 11, "y": 2026}
    update, context = make_update_and_context(
        user_id=111,
        chat_id=42,
        pending=pending,
        classify_result=ClassificationResult(kind="propose_new_item", item=second_item),
    )
    await handle_text_message(update, context)
    assert pending.pop(42) == second_item


@pytest.mark.asyncio
async def test_handle_confirmation_callback_confirm_creates_item_and_reports_success():
    pending = PendingProposals()
    pending.set(42, {"title": "מבחן"})
    update, context = make_update_and_context(chat_id=42, pending=pending, callback_data="confirm")
    context.bot_data["school_tl_client"].create_item = AsyncMock(return_value={"id": "new-1", "title": "מבחן"})
    await handle_confirmation_callback(update, context)
    context.bot_data["school_tl_client"].create_item.assert_awaited_once_with({"title": "מבחן"})
    update.callback_query.edit_message_text.assert_awaited_once()
    assert "new-1" in update.callback_query.edit_message_text.call_args.args[0]


@pytest.mark.asyncio
async def test_handle_confirmation_callback_confirm_reports_school_tl_error():
    pending = PendingProposals()
    pending.set(42, {"title": "מבחן"})
    update, context = make_update_and_context(chat_id=42, pending=pending, callback_data="confirm")
    context.bot_data["school_tl_client"].create_item = AsyncMock(side_effect=SchoolTLError(400, "title is required"))
    await handle_confirmation_callback(update, context)
    assert "title is required" in update.callback_query.edit_message_text.call_args.args[0]


@pytest.mark.asyncio
async def test_handle_confirmation_callback_cancel_discards_pending_without_writing():
    pending = PendingProposals()
    pending.set(42, {"title": "מבחן"})
    update, context = make_update_and_context(chat_id=42, pending=pending, callback_data="cancel")
    await handle_confirmation_callback(update, context)
    context.bot_data["school_tl_client"].create_item.assert_not_called()
    assert pending.pop(42) is None
