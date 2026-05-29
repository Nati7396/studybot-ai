import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from bot.database.db import delete_user_documents
from bot.services.vector_service import delete_user_index
from bot.utils.helpers import delete_user_files

logger = logging.getLogger(__name__)


async def reset_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[
        InlineKeyboardButton("✅ Yes, delete everything", callback_data="reset_confirm"),
        InlineKeyboardButton("❌ Cancel", callback_data="reset_cancel"),
    ]]
    await update.message.reply_text(
        "⚠️ *Are you sure?*\n\nThis will delete ALL your uploaded files, indexes, and session data.\n\nThis cannot be undone!",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )


async def reset_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    if query.data == "reset_confirm":
        try:
            delete_user_documents(user_id)
            delete_user_index(user_id)
            delete_user_files(user_id)
            await query.edit_message_text(
                "✅ *All your data has been deleted.*\n\nFresh start! Upload new PDFs anytime.",
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"Reset error: {e}")
            await query.edit_message_text(f"❌ Error during reset: {e}")
    else:
        await query.edit_message_text("❌ Reset cancelled. Your data is safe.")
