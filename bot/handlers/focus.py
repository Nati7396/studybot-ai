import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from bot.database.db import get_session, save_session

logger = logging.getLogger(__name__)


async def focus_full_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    session = get_session(user_id)
    session["study_focus"] = ""
    session["mode"] = "idle"
    save_session(user_id, session)

    await query.edit_message_text(
        "✅ *Full Module mode set!*\n\n"
        "All commands (summary, quiz, questions, exams) will cover your entire uploaded material.\n\n"
        "Use /focus anytime to change the scope.",
        parse_mode="Markdown"
    )


async def focus_specific_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    session = get_session(user_id)
    session["mode"] = "awaiting_focus"
    save_session(user_id, session)

    await query.edit_message_text(
        "🎯 *Specific Section Mode*\n\n"
        "Tell me which chapters or sections to focus on.\n\n"
        "Examples:\n"
        "• `Chapter 3 to Chapter 5`\n"
        "• `Unit 2 only`\n"
        "• `Pages 40 to 90`\n"
        "• `Chapters 1, 3, and 7`\n\n"
        "Just type your answer below 👇",
        parse_mode="Markdown"
    )


async def focus_text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Catches the user's text reply when awaiting a focus range."""
    user_id = update.effective_user.id
    session = get_session(user_id)

    if session.get("mode") != "awaiting_focus":
        return

    focus_text = update.message.text.strip()
    session["study_focus"] = focus_text
    session["mode"] = "idle"
    save_session(user_id, session)

    await update.message.reply_text(
        f"🎯 *Focus set: {focus_text}*\n\n"
        f"All commands (summary, quiz, questions, exams) will now focus only on *{focus_text}*.\n\n"
        f"Use /focus to change this anytime.",
        parse_mode="Markdown"
    )


async def focus_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Let the user change their study focus at any time."""
    user_id = update.effective_user.id
    session = get_session(user_id)
    current = session.get("study_focus", "")

    current_label = f"🎯 Current focus: *{current}*" if current else "📚 Current focus: *Full Module*"

    await update.message.reply_text(
        f"📌 *Study Focus*\n\n{current_label}\n\n"
        f"Change your focus scope:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [
                InlineKeyboardButton("📚 Full Module", callback_data="focus_full"),
                InlineKeyboardButton("🎯 Specific Section", callback_data="focus_specific"),
            ]
        ])
    )
