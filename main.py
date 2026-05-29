import logging
import os
import sys

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("studybot.log", encoding="utf-8"),
    ]
)
logger = logging.getLogger(__name__)

os.makedirs("bot/uploads", exist_ok=True)
os.makedirs("bot/vectorstore", exist_ok=True)
os.makedirs("bot/database", exist_ok=True)
os.makedirs("bot/webapp_data", exist_ok=True)

from telegram import Update
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, filters
)

from bot.config import TELEGRAM_BOT_TOKEN
from bot.database.db import init_db
from bot.handlers.start import start_handler, help_handler
from bot.handlers.upload import upload_command, document_handler
from bot.handlers.focus import (
    focus_full_callback, focus_specific_callback,
    focus_text_handler, focus_command
)
from bot.handlers.study import (
    status_handler, summary_handler, questions_handler, questions_count_callback,
    notes_handler, mockexam_handler, finalexam_handler,
    important_handler, predict_handler, onenighter_handler,
    explain_handler, examstyle_handler, webapp_handler
)
from bot.handlers.quiz import (
    quiz_handler, quiz_start_callback, quiz_retry_callback,
    flashcards_handler, flashcard_start_callback, flashcard_callback
)
from bot.handlers.reset import reset_handler, reset_callback


def main():
    if not TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN is not set!")
        sys.exit(1)

    logger.info("Initializing database...")
    init_db()

    logger.info("Starting StudyBot AI...")
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start_handler))
    app.add_handler(CommandHandler("help", help_handler))
    app.add_handler(CommandHandler("upload", upload_command))
    app.add_handler(CommandHandler("focus", focus_command))
    app.add_handler(CommandHandler("status", status_handler))
    app.add_handler(CommandHandler("summary", summary_handler))
    app.add_handler(CommandHandler("questions", questions_handler))
    app.add_handler(CommandHandler("notes", notes_handler))
    app.add_handler(CommandHandler("mockexam", mockexam_handler))
    app.add_handler(CommandHandler("finalexam", finalexam_handler))
    app.add_handler(CommandHandler("important", important_handler))
    app.add_handler(CommandHandler("predict", predict_handler))
    app.add_handler(CommandHandler("onenighter", onenighter_handler))
    app.add_handler(CommandHandler("quiz", quiz_handler))
    app.add_handler(CommandHandler("flashcards", flashcards_handler))
    app.add_handler(CommandHandler("reset", reset_handler))
    app.add_handler(CommandHandler("explain", explain_handler))
    app.add_handler(CommandHandler("examstyle", examstyle_handler))
    app.add_handler(CommandHandler("app", webapp_handler))

    app.add_handler(MessageHandler(filters.Document.ALL, document_handler))

    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        focus_text_handler
    ))

    app.add_handler(CallbackQueryHandler(focus_full_callback, pattern="^focus_full$"))
    app.add_handler(CallbackQueryHandler(focus_specific_callback, pattern="^focus_specific$"))
    app.add_handler(CallbackQueryHandler(quiz_start_callback, pattern="^quiz_start_"))
    app.add_handler(CallbackQueryHandler(quiz_retry_callback, pattern="^quiz_retry$|^quiz_go_flash$"))
    app.add_handler(CallbackQueryHandler(flashcard_start_callback, pattern="^fc_start_"))
    app.add_handler(CallbackQueryHandler(flashcard_callback, pattern="^fc_"))
    app.add_handler(CallbackQueryHandler(reset_callback, pattern="^reset_"))
    app.add_handler(CallbackQueryHandler(questions_count_callback, pattern="^gen_q_"))

    logger.info("StudyBot AI is running!")
    app.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)


if __name__ == "__main__":
    main()
