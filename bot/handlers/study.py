import logging
import os
import time
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo, Poll
from telegram.ext import ContextTypes
from bot.services.vector_service import has_documents, get_all_chunks
from bot.services.ai_service import (
    generate_summary, generate_questions, generate_short_notes,
    generate_mock_exam, generate_important_concepts, predict_exam_questions,
    generate_one_night_summary, explain_concept, analyze_exam_style,
    generate_quiz_questions, _rate_limited
)
from bot.services.webapp_service import save_webapp_data
from bot.utils.helpers import chunk_message
from bot.database.db import get_user_documents, get_session
from bot.config import GEMINI_API_KEYS

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


def _focus_label(focus: str) -> str:
    return f"🎯 Focus: *{focus}*" if focus else "📚 Scope: Full Module"


async def _check_docs(update: Update, user_id: int) -> bool:
    if not has_documents(user_id):
        await update.message.reply_text(_no_docs_msg())
        return False
    return True


async def status_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    docs = get_user_documents(user_id)
    chunks = get_all_chunks(user_id) if docs else []

    session = get_session(user_id)
    focus = session.get("study_focus", "")

    now = time.time()
    key_lines = []
    total_keys = len(GEMINI_API_KEYS)
    working_keys = 0
    from bot.services.ai_service import MODEL_PRIORITY
    for i in range(total_keys):
        all_limited = all(
            now < _rate_limited.get((i, m), 0) for m in MODEL_PRIORITY
        )
        if all_limited:
            soonest = min(_rate_limited.get((i, m), 0) for m in MODEL_PRIORITY)
            mins = int((soonest - now) // 60)
            key_lines.append(f"🔴 Key #{i+1} — rate-limited (~{mins}m left)")
        else:
            working_keys += 1
            key_lines.append(f"🟢 Key #{i+1} — active (1,500 req/day)")

    ai_status = "\n".join(key_lines)
    ai_summary = f"✅ {working_keys}/{total_keys} keys working" if working_keys else f"⚠️ All {total_keys} keys rate-limited"

    if not docs:
        files_section = "📭 No files uploaded yet — send a file or use /upload"
    else:
        doc_list = "\n".join([
            f"• {d['original_name']} ({d['page_count']} pages)"
            for d in docs
        ])
        files_section = f"{doc_list}\n\n📊 {len(docs)} file(s) | 🧩 {len(chunks)} study chunks"

    focus_section = f"\n─────────────────\n*📌 Study Focus*\n{_focus_label(focus)}\nUse /focus to change"

    keyboard = []
    if WEBAPP_URL:
        keyboard = [[InlineKeyboardButton("📖 Open Study App", web_app=WebAppInfo(url=WEBAPP_URL))]]

    await update.message.reply_text(
        f"📡 *Bot Status*\n\n"
        f"*🤖 AI Keys ({ai_summary})*\n"
        f"{ai_status}\n\n"
        f"💡 Add more keys as `GEMINI_API_KEY_2`, `GEMINI_API_KEY_3` etc.\n"
        f"Each key = +1,500 free requests/day\n\n"
        f"─────────────────\n"
        f"*📚 Your Study Files*\n"
        f"{files_section}"
        f"{focus_section}",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard) if keyboard else None
    )


async def summary_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not await _check_docs(update, user_id):
        return

    session = get_session(user_id)
    focus = session.get("study_focus", "")

    msg = await update.message.reply_text(
        f"🧠 Generating your summary...\n{_focus_label(focus)}\nThis may take a moment.",
        parse_mode="Markdown"
    )
    try:
        summary = generate_summary(user_id, focus=focus)
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

    session = get_session(user_id)
    focus = session.get("study_focus", "")

    keyboard = [
        [
            InlineKeyboardButton("10 Questions", callback_data="gen_q_10"),
            InlineKeyboardButton("20 Questions", callback_data="gen_q_20"),
        ],
        [
            InlineKeyboardButton("30 Questions", callback_data="gen_q_30"),
            InlineKeyboardButton("50 Questions", callback_data="gen_q_50"),
        ],
    ]
    await update.message.reply_text(
        f"📝 *Practice Questions*\n\n"
        f"{_focus_label(focus)}\n\n"
        f"How many questions do you want?\n"
        f"MCQs will appear as Telegram quiz polls — tap to answer!\n\n"
        f"Use /focus to change the chapter scope.",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )


async def questions_count_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    count = int(query.data.split("_")[-1])

    session = get_session(user_id)
    focus = session.get("study_focus", "")

    await query.edit_message_text(
        f"📝 Generating {count} questions...\n"
        f"{_focus_label(focus)}\n⏳ 30-60 seconds — worth it!"
    )
    try:
        questions = generate_quiz_questions(user_id, count=count, focus=focus)
        if not questions:
            await query.edit_message_text("❌ Couldn't generate questions. Try uploading more content.")
            return

        await query.edit_message_text(
            f"✅ *{len(questions)} questions ready!* Sending them now...",
            parse_mode="Markdown"
        )

        chat_id = query.message.chat_id
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
                explanation = (q.get("explanation", "") or "")[:200] or None

                await context.bot.send_poll(
                    chat_id=chat_id,
                    question=f"Q{i+1}. {question_text}"[:300],
                    options=[o[:100] for o in options],
                    type=Poll.QUIZ,
                    correct_option_id=correct_idx,
                    explanation=explanation,
                    is_anonymous=False,
                )
                sent += 1
            except Exception as e:
                logger.error(f"Poll send error Q{i+1}: {e}")

        await query.message.reply_text(
            f"✅ *{sent} questions sent above!*\n\n"
            f"{_focus_label(focus)}\n\n"
            f"Tap any answer to see if you're right.\n"
            f"Use /questions to generate more or /focus to change chapters.",
            parse_mode="Markdown"
        )

        save_webapp_data(user_id, "questions", [q.get("question", "") for q in questions])

    except Exception as e:
        logger.error(f"Questions error: {e}")
        await query.edit_message_text(f"❌ Error: {e}")


async def notes_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not await _check_docs(update, user_id):
        return

    session = get_session(user_id)
    focus = session.get("study_focus", "")

    msg = await update.message.reply_text(
        f"📋 Creating your short notes...\n{_focus_label(focus)}",
        parse_mode="Markdown"
    )
    try:
        notes = generate_short_notes(user_id, focus=focus)
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

    session = get_session(user_id)
    focus = session.get("study_focus", "")

    msg = await update.message.reply_text(
        f"🧪 Generating your mock mid exam...\n{_focus_label(focus)}",
        parse_mode="Markdown"
    )
    try:
        questions = generate_quiz_questions(user_id, count=15, focus=focus)
        await msg.delete()

        if questions:
            await update.message.reply_text(
                f"🧪 *MOCK MID EXAM*\n{_focus_label(focus)}\n\n"
                f"*Section A — MCQ Questions*\n"
                f"Tap your answer on each question below:",
                parse_mode="Markdown"
            )
            chat_id = update.effective_chat.id
            for i, q in enumerate(questions):
                try:
                    options = [q.get("a", ""), q.get("b", ""), q.get("c", ""), q.get("d", "")]
                    answer_map = {"A": 0, "B": 1, "C": 2, "D": 3}
                    correct_idx = answer_map.get(q.get("answer", "A").upper(), 0)
                    explanation = (q.get("explanation", "") or "")[:200] or None

                    await context.bot.send_poll(
                        chat_id=chat_id,
                        question=f"Q{i+1}. {q.get('question', '')}",
                        options=[o[:100] for o in options],
                        type=Poll.QUIZ,
                        correct_option_id=correct_idx,
                        explanation=explanation,
                        is_anonymous=False,
                    )
                except Exception as e:
                    logger.error(f"Mock exam poll error: {e}")

            exam_text = generate_mock_exam(user_id, exam_type="mid", focus=focus)
            save_webapp_data(user_id, "mock_mid_exam", exam_text)
            await update.message.reply_text(
                f"📝 *Section B & C — Written Questions*\n\n{exam_text[:3800]}",
                parse_mode="Markdown"
            )
        else:
            exam_text = generate_mock_exam(user_id, exam_type="mid", focus=focus)
            save_webapp_data(user_id, "mock_mid_exam", exam_text)
            header = f"🧪 *MOCK MID EXAM*\n{_focus_label(focus)}\n\n"
            for part in chunk_message(header + exam_text):
                await update.message.reply_text(part, parse_mode="Markdown")

    except Exception as e:
        logger.error(f"Mock exam error: {e}")
        await msg.edit_text(f"❌ Error: {e}")


async def finalexam_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not await _check_docs(update, user_id):
        return

    session = get_session(user_id)
    focus = session.get("study_focus", "")

    msg = await update.message.reply_text(
        f"🎓 Generating your mock final exam...\n{_focus_label(focus)}",
        parse_mode="Markdown"
    )
    try:
        questions = generate_quiz_questions(user_id, count=20, focus=focus)
        await msg.delete()

        if questions:
            await update.message.reply_text(
                f"🎓 *MOCK FINAL EXAM*\n{_focus_label(focus)}\n\n"
                f"*Section A — MCQ Questions*\n"
                f"Tap your answer on each question below:",
                parse_mode="Markdown"
            )
            chat_id = update.effective_chat.id
            for i, q in enumerate(questions):
                try:
                    options = [q.get("a", ""), q.get("b", ""), q.get("c", ""), q.get("d", "")]
                    answer_map = {"A": 0, "B": 1, "C": 2, "D": 3}
                    correct_idx = answer_map.get(q.get("answer", "A").upper(), 0)
                    explanation = (q.get("explanation", "") or "")[:200] or None

                    await context.bot.send_poll(
                        chat_id=chat_id,
                        question=f"Q{i+1}. {q.get('question', '')}",
                        options=[o[:100] for o in options],
                        type=Poll.QUIZ,
                        correct_option_id=correct_idx,
                        explanation=explanation,
                        is_anonymous=False,
                    )
                except Exception as e:
                    logger.error(f"Final exam poll error: {e}")

            exam_text = generate_mock_exam(user_id, exam_type="final", focus=focus)
            save_webapp_data(user_id, "mock_final_exam", exam_text)
            await update.message.reply_text(
                f"📝 *Section B, C & D — Written Questions*\n\n{exam_text[:3800]}",
                parse_mode="Markdown"
            )
        else:
            exam_text = generate_mock_exam(user_id, exam_type="final", focus=focus)
            save_webapp_data(user_id, "mock_final_exam", exam_text)
            header = f"🎓 *MOCK FINAL EXAM*\n{_focus_label(focus)}\n\n"
            for part in chunk_message(header + exam_text):
                await update.message.reply_text(part, parse_mode="Markdown")

    except Exception as e:
        logger.error(f"Final exam error: {e}")
        await msg.edit_text(f"❌ Error: {e}")


async def important_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not await _check_docs(update, user_id):
        return

    session = get_session(user_id)
    focus = session.get("study_focus", "")

    msg = await update.message.reply_text(
        f"🔍 Analyzing must-know concepts...\n{_focus_label(focus)}",
        parse_mode="Markdown"
    )
    try:
        result = generate_important_concepts(user_id, focus=focus)
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

    session = get_session(user_id)
    focus = session.get("study_focus", "")

    msg = await update.message.reply_text(
        f"🔮 Predicting likely exam questions...\n{_focus_label(focus)}",
        parse_mode="Markdown"
    )
    try:
        result = predict_exam_questions(user_id, focus=focus)
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

    session = get_session(user_id)
    focus = session.get("study_focus", "")

    msg = await update.message.reply_text(
        f"🌙 Creating your one-night-before summary...\n{_focus_label(focus)}",
        parse_mode="Markdown"
    )
    try:
        result = generate_one_night_summary(user_id, focus=focus)
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

    session = get_session(user_id)
    focus = session.get("study_focus", "")

    msg = await update.message.reply_text(
        f"🎓 *Analyzing exam style...*\n{_focus_label(focus)}",
        parse_mode="Markdown"
    )
    try:
        result = analyze_exam_style(user_id, focus=focus)
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
