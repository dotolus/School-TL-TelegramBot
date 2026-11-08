from datetime import date

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CallbackQueryHandler, MessageHandler, filters

from bot.claude_assistant import answer_query as real_answer_query
from bot.claude_assistant import classify_message as real_classify_message
from bot.formatting import format_item_summary
from bot.school_tl_client import SchoolTLError

UNAUTHORIZED_MESSAGE = "אין לך הרשאה להשתמש בבוט הזה."
DECLINE_EDIT_MESSAGE = "עדיין אין תמיכה בעריכת פריטים קיימים — זה יתאפשר בעתיד."
NOTHING_PENDING_MESSAGE = "אין הצעה שמחכה לאישור."
CANCELLED_MESSAGE = "בוטל."
STALE_PROPOSAL_MESSAGE = "ההצעה הזו הוחלפה בהצעה חדשה יותר — התעלמתי מהבחירה."
GENERIC_FAILURE_MESSAGE = "קרתה תקלה בעיבוד ההודעה. נסה שוב בעוד רגע."


async def handle_text_message(update, context):
    if update.effective_user is None or update.message is None:
        # A channel post has no originating user; an edited message has no
        # `message` (only `edited_message`). Neither can be authorized or
        # replied to the normal way, so there is nothing safe to do here.
        return

    config = context.bot_data["config"]
    if update.effective_user.id not in config.allowed_user_ids:
        await update.message.reply_text(UNAUTHORIZED_MESSAGE)
        return

    claude_client = context.bot_data["claude_client"]
    classify_message = context.bot_data["classify_message"]
    try:
        result = await classify_message(claude_client, config.claude_model, update.message.text, date.today())
    except Exception:
        await update.message.reply_text(GENERIC_FAILURE_MESSAGE)
        return

    if result.kind == "query":
        try:
            school_tl_client = context.bot_data["school_tl_client"]
            items = await school_tl_client.get_timeline()
            answer_query = context.bot_data["answer_query"]
            answer = await answer_query(
                claude_client, config.claude_model, update.message.text, items, date.today()
            )
        except Exception:
            await update.message.reply_text(GENERIC_FAILURE_MESSAGE)
            return
        await update.message.reply_text(answer)
    elif result.kind == "propose_new_item":
        pending = context.bot_data["pending"]
        token = pending.set(update.effective_chat.id, result.item)
        keyboard = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton("אישור", callback_data=f"confirm:{token}"),
                    InlineKeyboardButton("ביטול", callback_data=f"cancel:{token}"),
                ]
            ]
        )
        await update.message.reply_text(format_item_summary(result.item), reply_markup=keyboard)
    else:
        await update.message.reply_text(DECLINE_EDIT_MESSAGE)


async def handle_confirmation_callback(update, context):
    config = context.bot_data["config"]
    if update.effective_user.id not in config.allowed_user_ids:
        return

    pending = context.bot_data["pending"]
    chat_id = update.effective_chat.id
    action, _, token = update.callback_query.data.partition(":")

    current_token = pending.peek_token(chat_id)
    if current_token is None:
        await update.callback_query.edit_message_text(NOTHING_PENDING_MESSAGE)
        return
    if current_token != token:
        await update.callback_query.edit_message_text(STALE_PROPOSAL_MESSAGE)
        return

    if action != "confirm":
        pending.pop(chat_id, token)
        await update.callback_query.edit_message_text(CANCELLED_MESSAGE)
        return

    item = pending.pop(chat_id, token)
    school_tl_client = context.bot_data["school_tl_client"]
    try:
        created = await school_tl_client.create_item(item)
    except SchoolTLError as error:
        await update.callback_query.edit_message_text(f"יצירת הפריט נכשלה: {error.message}")
        return
    except Exception:
        await update.callback_query.edit_message_text(GENERIC_FAILURE_MESSAGE)
        return
    await update.callback_query.edit_message_text(f"הפריט נוצר בהצלחה (מזהה: {created['id']}).")


def build_application(config, school_tl_client, claude_client, pending):
    application = Application.builder().token(config.telegram_bot_token).build()
    application.bot_data.update(
        {
            "config": config,
            "school_tl_client": school_tl_client,
            "claude_client": claude_client,
            "pending": pending,
            "classify_message": real_classify_message,
            "answer_query": real_answer_query,
        }
    )
    application.add_handler(
        MessageHandler(filters.UpdateType.MESSAGE & filters.TEXT & ~filters.COMMAND, handle_text_message)
    )
    application.add_handler(CallbackQueryHandler(handle_confirmation_callback))
    return application
