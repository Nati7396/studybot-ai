import logging
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import ContextTypes
from bot.services.vector_service import has_documents, get_all_chunks
from bot.services.ai_service import (
    generate_summary, generate_questions, generate_short_notes,
    generate_mock_exam, generate_important_concepts, predict_exam_questions,
    generate_one_night_summary, explain_concept, analyze_exam_style
)
from bot.services.webapp_service import save_webapp_data
from bot.utils.helpers import chunk_message
from bot.database.db import get_user_documents

logger = logging.getLogger(__name__)

REPLIT_DOMAIN = os.getenv("REPLIT_DEV_DOMAIN", "")
WEBAPP_URL = f"https://{REPLIT_DOMAIN}/study" if REPLIT_DOMAIN else ""


def _no_docs_msg():
    return (
        "📭 No study materials found!\n\n"
        "Upload your PDFs first:\n"
        "Just send a PDF file in this chat, or use /upload\n\n"
        "The more you upload, the better I can help!"
    )


async def _check_docs(update: Update, user_id: int) -> bool:
    if not has_documents(user_id):
        await update.message.reply_text(_no_docs_msg())
        return False
    return True


async def status_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    docs = get_user_documents(user_id)

    if not docs:
        await update.message.reply_text(_no_docs_msg())
        return

    chunks = get_all_chunks(user_id)
    doc_list = "\n".join([
        f"• {d['original_name']} ({d['page_count']} pages)"
        for d in docs
    ])

    keyboard = []
    if WEBAPP_URL:
        keyboard = [[InlineKeyboardButton("📖 Open Study App", web_app=WebAppInfo(url=WEBAPP_URL))]]

    await update.message.reply_text(
        f"📚 *Your Study Materials*\n\n"
        f"{doc_list}\n\n"
        f"📊 Total files: {len(docs)}\n"
        f"🧩 Study chunks indexed: {len(chunks)}\n\n"
        f"Use /summary, /questions, /quiz or /mockexam to study!",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard) if keyboard else None
    )


async def summary_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not await _check_docs(update, user_id):
        return

    msg = await update.message.reply_text("🧠 Generating your summary... This may take a moment.")
    try:
        summary = generate_summary(user_id)
        save_webapp_data(user_id, "summary", summary)
        await msg.delete()
        for part in chunk_message(summary):
            await update.message.reply_text(part)
        if WEBAPP_URL:
            await update.message.reply_text(
                "📖 View your full notes in the Study App:",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("Open Study App 📚", web_app=WebAppInfo(url=WEBAPP_URL))
                ]])
            )
    except Exception as e:
        logger.error(f"Summary error: {e}")
        await msg.edit_text(f"❌ Error generating summary: {e}")


async def questions_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not await _check_docs(update, user_id):
        return

    keyboard = [
        [
            InlineKeyboardButton("20 Questions", callback_data="gen_q_20"),
            InlineKeyboardButton("50 Questions", callback_data="gen_q_50"),
        ],
        [
            InlineKeyboardButton("100 Questions", callback_data="gen_q_100"),
        ]
    ]
    await update.message.reply_text(
        "📝 *Generate Practice Questions*\n\nHow many questions do you want?",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )


async def questions_count_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    count = int(query.data.split("_")[-1])

    await query.edit_message_text(
        f"📝 Generating {count} practice questions...\n⏳ This takes 30-60 seconds — worth it!"
    )
    try:
        questions = generate_questions(user_id, count=count)
        if not questions:
            await query.edit_message_text("❌ Couldn't generate questions. Try uploading more content.")
            return

        save_webapp_data(user_id, "questions", [q["text"] for q in questions])
        await query.edit_message_text(f"✅ {len(questions)} questions generated! Sending now...")

        header = f"📝 *{len(questions)} Practice Questions*\n\n"
        q_text = header + "\n\n".join([q["text"] for q in questions])
        for part in chunk_message(q_text):
            await query.message.reply_text(part, parse_mode="Markdown")

        if WEBAPP_URL:
            await query.message.reply_text(
                "📖 View all questions in the Study App:",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("Open Study App 📚", web_app=WebAppInfo(url=WEBAPP_URL))
                ]])
            )
    except Exception as e:
        logger.error(f"Questions error: {e}")
        await query.edit_message_text(f"❌ Error: {e}")


async def notes_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not await _check_docs(update, user_id):
        return

    msg = await update.message.reply_text("📋 Creating your short notes...")
    try:
        notes = generate_short_notes(user_id)
        save_webapp_data(user_id, "notes", notes)
        await msg.delete()
        for part in chunk_message(notes):
            await update.message.reply_text(part)
        if WEBAPP_URL:
            await update.message.reply_text(
                "📖 View in dark mode Study App:",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("Open Study App 📚", web_app=WebAppInfo(url=WEBAPP_URL))
                ]])
            )
    except Exception as e:
        logger.error(f"Notes error: {e}")
        await msg.edit_text(f"❌ Error: {e}")


async def mockexam_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not await _check_docs(update, user_id):
        return

    msg = await update.message.reply_text("🧪 Generating your mock mid exam...")
    try:
        exam = generate_mock_exam(user_id, exam_type="mid")
        save_webapp_data(user_id, "mock_mid_exam", exam)
        await msg.delete()
        header = "🧪 *MOCK MID EXAM*\n\n"
        for part in chunk_message(header + exam):
            await update.message.reply_text(part, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Mock exam error: {e}")
        await msg.edit_text(f"❌ Error: {e}")


async def finalexam_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not await _check_docs(update, user_id):
        return

    msg = await update.message.reply_text("🎓 Generating your mock final exam...")
    try:
        exam = generate_mock_exam(user_id, exam_type="final")
        save_webapp_data(user_id, "mock_final_exam", exam)
        await msg.delete()
        header = "🎓 *MOCK FINAL EXAM*\n\n"
        for part in chunk_message(header + exam):
            await update.message.reply_text(part, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Final exam error: {e}")
        await msg.edit_text(f"❌ Error: {e}")


async def important_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not await _check_docs(update, user_id):
        return

    msg = await update.message.reply_text("🔍 Analyzing your materials for must-know concepts...")
    try:
        result = generate_important_concepts(user_id)
        save_webapp_data(user_id, "important_concepts", result)
        await msg.delete()
        for part in chunk_message(result):
            await update.message.reply_text(part)
    except Exception as e:
        logger.error(f"Important error: {e}")
        await msg.edit_text(f"❌ Error: {e}")


async def predict_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not await _check_docs(update, user_id):
        return

    msg = await update.message.reply_text("🔮 Predicting likely exam questions from your materials...")
    try:
        result = predict_exam_questions(user_id)
        save_webapp_data(user_id, "predictions", result)
        await msg.delete()
        header = "🔮 *Exam Question Predictions*\n\n"
        for part in chunk_message(header + result):
            await update.message.reply_text(part, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Predict error: {e}")
        await msg.edit_text(f"❌ Error: {e}")


async def onenighter_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not await _check_docs(update, user_id):
        return

    msg = await update.message.reply_text("🌙 Creating your one-night-before summary...")
    try:
        result = generate_one_night_summary(user_id)
        save_webapp_data(user_id, "one_nighter", result)
        await msg.delete()
        header = "🌙 *ONE NIGHT BEFORE EXAM — EMERGENCY GUIDE*\n\n"
        for part in chunk_message(header + result):
            await update.message.reply_text(part, parse_mode="Markdown")
        if WEBAPP_URL:
            await update.message.reply_text(
                "📖 Read in dark mode Study App:",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("Open Study App 📚", web_app=WebAppInfo(url=WEBAPP_URL))
                ]])
            )
    except Exception as e:
        logger.error(f"Onenighter error: {e}")
        await msg.edit_text(f"❌ Error: {e}")


async def explain_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    args = context.args

    if not args:
        await update.message.reply_text(
            "💡 Usage: /explain <concept>\n\nExample: /explain photosynthesis"
        )
        return

    concept = " ".join(args)
    msg = await update.message.reply_text(f"💡 Explaining *{concept}*...", parse_mode="Markdown")
    try:
        result = explain_concept(user_id, concept)
        await msg.delete()
        for part in chunk_message(result):
            await update.message.reply_text(part)
    except Exception as e:
        logger.error(f"Explain error: {e}")
        await msg.edit_text(f"❌ Error: {e}")


async def examstyle_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not await _check_docs(update, user_id):
        return

    msg = await update.message.reply_text(
        "🎓 *Analyzing your previous exam papers...*\n\n"
        "Detecting question styles, formats, and patterns to generate questions exactly like your university exams.",
        parse_mode="Markdown"
    )
    try:
        result = analyze_exam_style(user_id)
        save_webapp_data(user_id, "exam_style_questions", result)
        await msg.delete()
        header = "🎓 *EXAM-STYLE QUESTIONS*\n_(Based on your past exam patterns)_\n\n"
        for part in chunk_message(header + result):
            await update.message.reply_text(part, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Examstyle error: {e}")
        await msg.edit_text(f"❌ Error: {e}")


async def webapp_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not await _check_docs(update, user_id):
        return

    if not WEBAPP_URL:
        await update.message.reply_text(
            "⚠️ Study App URL not configured yet.\n\n"
            "Use /summary, /notes, or /questions to study right here in the chat!"
        )
        return

    await update.message.reply_text(
        "📚 *Open your Study App*\n\nDark mode notes, questions & flashcards — all in one place.",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("📖 Open Study App", web_app=WebAppInfo(url=WEBAPP_URL))
        ]])
    )
