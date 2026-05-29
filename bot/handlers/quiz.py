import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, Poll
from telegram.ext import ContextTypes
from bot.services.vector_service import has_documents
from bot.services.ai_service import generate_quiz_questions, generate_flashcards
from bot.database.db import get_session, save_session

logger = logging.getLogger(__name__)


def _no_docs_msg():
    return "📭 No study materials! Upload PDFs first."


def _focus_label(focus: str) -> str:
    return f"🎯 Focus: {focus}" if focus else "📚 Full Module"


async def quiz_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not has_documents(user_id):
        await update.effective_message.reply_text(_no_docs_msg())
        return

    session = get_session(user_id)
    focus = session.get("study_focus", "")

    keyboard = [
        [
            InlineKeyboardButton("10 Questions", callback_data="quiz_start_10"),
            InlineKeyboardButton("20 Questions", callback_data="quiz_start_20"),
        ],
        [
            InlineKeyboardButton("30 Questions", callback_data="quiz_start_30"),
            InlineKeyboardButton("50 Questions", callback_data="quiz_start_50"),
        ],
    ]
    await update.effective_message.reply_text(
        f"🎯 *Quiz Mode*\n\n"
        f"{_focus_label(focus)}\n\n"
        f"How many questions do you want?\n"
        f"Each question will appear as a Telegram quiz — tap your answer to see if you're right!\n\n"
        f"Use /focus to change the chapter scope.",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )


async def quiz_start_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    count = int(query.data.split("_")[-1])

    session = get_session(user_id)
    focus = session.get("study_focus", "")

    await query.edit_message_text(
        f"⏳ Generating {count} quiz questions...\n"
        f"{_focus_label(focus)}\n\n"
        f"This takes about 20-40 seconds — sit tight!"
    )

    try:
        questions = generate_quiz_questions(user_id, count=count, focus=focus)
        if not questions:
            await query.edit_message_text("❌ Couldn't generate questions. Try uploading more content.")
            return

        await query.edit_message_text(
            f"🎯 *{len(questions)} Quiz Questions Ready!*\n\n"
            f"{_focus_label(focus)}\n\n"
            f"Sending them now — tap your answer on each question!\n"
            f"Telegram will show you instantly if you're right ✅ or wrong ❌",
            parse_mode="Markdown"
        )

        await _send_quiz_polls(query.message, context, user_id, questions)

    except Exception as e:
        logger.error(f"Quiz start error: {e}")
        await query.edit_message_text(f"❌ Error starting quiz: {e}")


async def _send_quiz_polls(message, context: ContextTypes.DEFAULT_TYPE, user_id: int, questions: list):
    """Send each MCQ question as a native Telegram quiz poll."""
    chat_id = message.chat_id
    sent = 0

    for i, q in enumerate(questions):
        try:
            question_text = q.get("question", "")
            if not question_text:
                continue

            options = [
                q.get("a", "Option A"),
                q.get("b", "Option B"),
                q.get("c", "Option C"),
                q.get("d", "Option D"),
            ]

            answer_map = {"A": 0, "B": 1, "C": 2, "D": 3}
            correct_idx = answer_map.get(q.get("answer", "A").upper(), 0)

            explanation = q.get("explanation", "") or ""

            question_text = question_text[:300]
            options = [o[:100] for o in options]
            explanation = explanation[:200] if explanation else None

            await context.bot.send_poll(
                chat_id=chat_id,
                question=f"Q{i+1}. {question_text}"[:300],
                options=options,
                type=Poll.QUIZ,
                correct_option_id=correct_idx,
                explanation=explanation,
                is_anonymous=False,
                protect_content=False,
            )
            sent += 1

        except Exception as e:
            logger.error(f"Error sending poll Q{i+1}: {e}")
            continue

    if sent > 0:
        await message.reply_text(
            f"✅ *{sent} quiz questions sent above!*\n\n"
            f"Tap any answer to see if you're right.\n"
            f"Use /quiz to try again or /focus to change chapters.",
            parse_mode="Markdown"
        )
    else:
        await message.reply_text("❌ Couldn't send quiz polls. Please try again.")


async def quiz_retry_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "quiz_retry":
        await query.edit_message_text("Starting a new quiz!")
        keyboard = [
            [
                InlineKeyboardButton("10 Questions", callback_data="quiz_start_10"),
                InlineKeyboardButton("20 Questions", callback_data="quiz_start_20"),
            ],
            [
                InlineKeyboardButton("30 Questions", callback_data="quiz_start_30"),
                InlineKeyboardButton("50 Questions", callback_data="quiz_start_50"),
            ],
        ]
        await query.message.reply_text(
            "🎯 *New Quiz — How many questions?*",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
    elif query.data == "quiz_go_flash":
        await query.edit_message_text("Switching to flashcards...")
        await flashcards_handler_from_callback(query.message, query.from_user.id)


async def flashcards_handler_from_callback(message, user_id: int):
    if not has_documents(user_id):
        await message.reply_text(_no_docs_msg())
        return
    msg = await message.reply_text("🃏 Generating flashcards...")
    try:
        session = get_session(user_id)
        focus = session.get("study_focus", "")
        cards = generate_flashcards(user_id, count=20, focus=focus)
        if not cards:
            await msg.edit_text("❌ Couldn't generate flashcards.")
            return
        session["flashcard_deck"] = cards
        session["flashcard_index"] = 0
        session["mode"] = "flashcards"
        save_session(user_id, session)
        await msg.delete()
        await message.reply_text(
            f"🃏 *{len(cards)} Flashcards Ready!*",
            parse_mode="Markdown"
        )
        await _send_flashcard(message, user_id, 0, cards)
    except Exception as e:
        await msg.edit_text(f"❌ Error: {e}")


async def flashcards_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not has_documents(user_id):
        await update.effective_message.reply_text(_no_docs_msg())
        return

    session = get_session(user_id)
    focus = session.get("study_focus", "")

    keyboard = [
        [
            InlineKeyboardButton("20 Cards", callback_data="fc_start_20"),
            InlineKeyboardButton("30 Cards", callback_data="fc_start_30"),
            InlineKeyboardButton("50 Cards", callback_data="fc_start_50"),
        ]
    ]
    await update.effective_message.reply_text(
        f"🃏 *Flashcard Mode*\n\n{_focus_label(focus)}\n\nHow many cards do you want?",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )


async def flashcard_start_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    count = int(query.data.split("_")[-1])

    await query.edit_message_text(f"⏳ Generating {count} flashcards...")
    try:
        session = get_session(user_id)
        focus = session.get("study_focus", "")
        cards = generate_flashcards(user_id, count=count, focus=focus)
        if not cards:
            await query.edit_message_text("❌ Couldn't generate flashcards. Upload more content.")
            return
        session["flashcard_deck"] = cards
        session["flashcard_index"] = 0
        session["mode"] = "flashcards"
        save_session(user_id, session)
        await query.edit_message_text(f"🃏 *{len(cards)} Flashcards Ready!*", parse_mode="Markdown")
        await _send_flashcard(query.message, user_id, 0, cards)
    except Exception as e:
        await query.edit_message_text(f"❌ Error: {e}")


async def _send_flashcard(message, user_id: int, index: int, cards: list):
    if index >= len(cards):
        await message.reply_text(
            "🏁 *Deck complete!* Use /flashcards to go again.",
            parse_mode="Markdown"
        )
        return
    card = cards[index]
    text = f"🃏 *Card {index + 1}/{len(cards)}*\n\n📌 {card['front']}"
    keyboard = [[InlineKeyboardButton("👁️ Reveal Answer", callback_data=f"fc_show_{index}")]]
    await message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")


async def flashcard_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = query.data

    session = get_session(user_id)
    cards = session.get("flashcard_deck", [])

    if data.startswith("fc_show_"):
        index = int(data.split("_")[-1])
        if index >= len(cards):
            await query.edit_message_text("Session expired. Use /flashcards to restart.")
            return
        card = cards[index]
        text = (
            f"🃏 *Card {index + 1}/{len(cards)}*\n\n"
            f"📌 *{card['front']}*\n\n"
            f"💡 {card['back']}"
        )
        next_idx = index + 1
        if next_idx < len(cards):
            keyboard = [[InlineKeyboardButton("Next Card ➡️", callback_data=f"fc_next_{next_idx}")]]
        else:
            keyboard = [[InlineKeyboardButton("🏁 Finish Deck", callback_data="fc_done")]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    elif data.startswith("fc_next_"):
        index = int(data.split("_")[-1])
        await query.edit_message_text(f"Loading card {index + 1}...")
        if index >= len(cards):
            await query.message.reply_text("🏁 Done! Use /flashcards to restart.")
            return
        card = cards[index]
        text = f"🃏 *Card {index + 1}/{len(cards)}*\n\n📌 {card['front']}"
        keyboard = [[InlineKeyboardButton("👁️ Reveal Answer", callback_data=f"fc_show_{index}")]]
        await query.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    elif data == "fc_done":
        await query.edit_message_text(
            "🏁 *Flashcard session complete!*\n\nUse /quiz to test yourself or /flashcards to go again.",
            parse_mode="Markdown"
        )
