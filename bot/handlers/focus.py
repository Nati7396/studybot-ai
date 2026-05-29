import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from bot.database.db import get_session, save_session

logger = logging.getLogger(__name__)


def _study_menu(focus: str) -> InlineKeyboardMarkup:
    scope = f"📌 {focus}" if focus else "📚 Full Module"
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🧠 Summary", callback_data="menu_summary"),
            InlineKeyboardButton("📋 Short Notes", callback_data="menu_notes"),
        ],
        [
            InlineKeyboardButton("🎯 Quiz", callback_data="menu_quiz"),
            InlineKeyboardButton("📝 Questions", callback_data="menu_questions"),
        ],
        [
            InlineKeyboardButton("🧪 Mock Mid Exam", callback_data="menu_mockexam"),
            InlineKeyboardButton("🎓 Final Exam", callback_data="menu_finalexam"),
        ],
        [
            InlineKeyboardButton("🔮 Predict Exam Qs", callback_data="menu_predict"),
            InlineKeyboardButton("🃏 Flashcards", callback_data="menu_flashcards"),
        ],
        [
            InlineKeyboardButton("🌙 One-Nighter", callback_data="menu_onenighter"),
            InlineKeyboardButton("🔍 Important Concepts", callback_data="menu_important"),
        ],
    ])


async def _show_study_menu(message, focus: str, edit: bool = False):
    text = (
        f"✅ *Focus set!*\n\n"
        f"{'🎯 ' + focus if focus else '📚 Full Module'}\n\n"
        f"What do you want to do? Tap below 👇"
    )
    if edit:
        await message.edit_text(text, parse_mode="Markdown", reply_markup=_study_menu(focus))
    else:
        await message.reply_text(text, parse_mode="Markdown", reply_markup=_study_menu(focus))


async def focus_full_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    session = get_session(user_id)
    session["study_focus"] = ""
    session["mode"] = "idle"
    save_session(user_id, session)

    await _show_study_menu(query, focus="", edit=True)


async def focus_specific_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    session = get_session(user_id)
    session["mode"] = "awaiting_focus"
    save_session(user_id, session)

    await query.edit_message_text(
        "🎯 *Which chapters or sections?*\n\n"
        "Examples:\n"
        "• `Chapter 3 to Chapter 5`\n"
        "• `Unit 2 only`\n"
        "• `Pages 40 to 90`\n"
        "• `Chapters 1, 3, and 7`\n\n"
        "Just type it below 👇",
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

    await _show_study_menu(update.message, focus=focus_text, edit=False)


async def focus_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Let the user change their study focus at any time."""
    user_id = update.effective_user.id
    session = get_session(user_id)
    current = session.get("study_focus", "")

    current_label = f"🎯 Current: *{current}*" if current else "📚 Current: *Full Module*"

    await update.message.reply_text(
        f"📌 *Study Focus*\n\n{current_label}\n\nChange scope:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [
                InlineKeyboardButton("📚 Full Module", callback_data="focus_full"),
                InlineKeyboardButton("🎯 Specific Section", callback_data="focus_specific"),
            ]
        ])
    )


async def menu_action_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle taps on the study menu buttons."""
    query = update.callback_query
    await query.answer()

    action = query.data.replace("menu_", "")

    from bot.handlers.study import (
        summary_handler, notes_handler, questions_handler,
        mockexam_handler, finalexam_handler, predict_handler,
        onenighter_handler, important_handler
    )
    from bot.handlers.quiz import quiz_handler, flashcards_handler

    handler_map = {
        "summary": summary_handler,
        "notes": notes_handler,
        "questions": questions_handler,
        "mockexam": mockexam_handler,
        "finalexam": finalexam_handler,
        "predict": predict_handler,
        "onenighter": onenighter_handler,
        "important": important_handler,
        "quiz": quiz_handler,
        "flashcards": flashcards_handler,
    }

    handler = handler_map.get(action)
    if handler:
        await query.edit_message_reply_markup(reply_markup=None)
        await handler(update, context)
