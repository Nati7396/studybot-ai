import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from bot.services.vector_service import has_documents
from bot.services.ai_service import generate_quiz_questions, generate_flashcards
from bot.database.db import get_session, save_session

logger = logging.getLogger(__name__)


def _no_docs_msg():
    return "📭 No study materials! Upload PDFs first."


async def quiz_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not has_documents(user_id):
        await update.message.reply_text(_no_docs_msg())
        return

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
    await update.message.reply_text(
        "🎯 *Quiz Mode*\n\nHow many questions do you want?\n\nYou'll be graded at the end!",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )


async def quiz_start_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    count = int(query.data.split("_")[-1])

    await query.edit_message_text(
        f"⏳ Generating {count} questions from your materials...\nThis takes about 20-40 seconds!"
    )

    try:
        questions = generate_quiz_questions(user_id, count=count)
        if not questions:
            await query.edit_message_text("❌ Couldn't generate questions. Try uploading more content.")
            return

        session = get_session(user_id)
        session["quiz_questions"] = questions
        session["quiz_index"] = 0
        session["quiz_score"] = 0
        session["quiz_total"] = len(questions)
        session["mode"] = "quiz"
        save_session(user_id, session)

        await query.edit_message_text(
            f"🎯 *Quiz Starting!*\n\n"
            f"📋 {len(questions)} questions\n"
            f"📚 Based on your uploaded materials\n\n"
            f"Answer each question — you'll see your score at the end!\n\n"
            f"Good luck! 🍀",
            parse_mode="Markdown"
        )
        await _send_question(query.message, user_id, 0, questions)

    except Exception as e:
        logger.error(f"Quiz start error: {e}")
        await query.edit_message_text(f"❌ Error starting quiz: {e}")


async def _send_question(message, user_id: int, index: int, questions: list):
    q = questions[index]
    total = len(questions)

    session = get_session(user_id)
    score = session.get("quiz_score", 0)

    text = (
        f"❓ *Question {index + 1} of {total}*\n"
        f"✅ Score so far: {score}/{index}\n\n"
        f"*{q['question']}*\n\n"
        f"🅐 {q['a']}\n"
        f"🅑 {q['b']}\n"
        f"🅒 {q['c']}\n"
        f"🅓 {q['d']}"
    )

    keyboard = [[
        InlineKeyboardButton("A", callback_data=f"qa_A_{index}"),
        InlineKeyboardButton("B", callback_data=f"qa_B_{index}"),
        InlineKeyboardButton("C", callback_data=f"qa_C_{index}"),
        InlineKeyboardButton("D", callback_data=f"qa_D_{index}"),
    ]]
    await message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")


async def quiz_answer_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    parts = query.data.split("_")
    selected = parts[1]
    index = int(parts[2])

    session = get_session(user_id)
    questions = session.get("quiz_questions", [])

    if index >= len(questions):
        await query.edit_message_text("⚠️ Session expired. Start a new /quiz")
        return

    q = questions[index]
    correct = q["answer"]
    is_correct = selected == correct
    total = len(questions)
    next_index = index + 1

    if is_correct:
        session["quiz_score"] = session.get("quiz_score", 0) + 1

    save_session(user_id, session)
    score = session["quiz_score"]

    option_labels = {"A": q["a"], "B": q["b"], "C": q["c"], "D": q["d"]}

    if is_correct:
        result = f"✅ *Correct!* Well done!\n\n"
    else:
        result = (
            f"❌ *Wrong!*\n\n"
            f"Your answer: {selected}) {option_labels[selected]}\n"
            f"✅ Correct answer: {correct}) {option_labels[correct]}\n\n"
        )

    if q.get("explanation"):
        result += f"💡 *Why:* {q['explanation']}\n\n"

    if next_index >= total:
        pct = round((score / total) * 100)
        if pct >= 90:
            grade = "🏆 Outstanding!"
        elif pct >= 75:
            grade = "🌟 Great job!"
        elif pct >= 60:
            grade = "👍 Good effort!"
        elif pct >= 40:
            grade = "📚 Keep studying!"
        else:
            grade = "💪 You'll get it next time!"

        result += f"📊 *Final Score: {score}/{total} ({pct}%)*\n{grade}"
        await query.edit_message_text(result, parse_mode="Markdown")

        session["mode"] = "idle"
        session["quiz_score"] = 0
        session["quiz_index"] = 0
        save_session(user_id, session)

        keyboard = [[
            InlineKeyboardButton("🔁 Try Again", callback_data="quiz_retry"),
            InlineKeyboardButton("🃏 Flashcards", callback_data="quiz_go_flash"),
        ]]
        await query.message.reply_text(
            "What's next?",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    else:
        result += f"➡️ Question {next_index + 1} coming up..."
        await query.edit_message_text(result, parse_mode="Markdown")
        session["quiz_index"] = next_index
        save_session(user_id, session)
        await _send_question(query.message, user_id, next_index, questions)


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
        cards = generate_flashcards(user_id, count=20)
        if not cards:
            await msg.edit_text("❌ Couldn't generate flashcards.")
            return
        session = get_session(user_id)
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
        await update.message.reply_text(_no_docs_msg())
        return

    keyboard = [
        [
            InlineKeyboardButton("20 Cards", callback_data="fc_start_20"),
            InlineKeyboardButton("30 Cards", callback_data="fc_start_30"),
            InlineKeyboardButton("50 Cards", callback_data="fc_start_50"),
        ]
    ]
    await update.message.reply_text(
        "🃏 *Flashcard Mode*\n\nHow many cards do you want?",
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
        cards = generate_flashcards(user_id, count=count)
        if not cards:
            await query.edit_message_text("❌ Couldn't generate flashcards. Upload more content.")
            return
        session = get_session(user_id)
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
