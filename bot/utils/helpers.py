import os
import shutil
import logging
from bot.config import UPLOAD_DIR

logger = logging.getLogger(__name__)


def format_file_size(size_bytes: int) -> str:
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    else:
        return f"{size_bytes / (1024 * 1024):.1f} MB"


def delete_user_files(user_id: int):
    user_dir = os.path.join(UPLOAD_DIR, str(user_id))
    if os.path.exists(user_dir):
        shutil.rmtree(user_dir)
        logger.info(f"Deleted files for user {user_id}")


def chunk_message(text: str, max_length: int = 4000) -> list[str]:
    """Split long messages for Telegram (4096 char limit)."""
    if len(text) <= max_length:
        return [text]

    parts = []
    while text:
        if len(text) <= max_length:
            parts.append(text)
            break
        split_at = text.rfind('\n', 0, max_length)
        if split_at == -1:
            split_at = max_length
        parts.append(text[:split_at])
        text = text[split_at:].lstrip('\n')
    return parts


def escape_markdown(text: str) -> str:
    """Escape special chars for Telegram MarkdownV2."""
    special = r'_*[]()~`>#+-=|{}.!'
    for char in special:
        text = text.replace(char, f'\\{char}')
    return text


WELCOME_MESSAGE = """👋 Welcome to *StudyBot AI* — your personal exam coach!

I help you study smarter from your own materials. Upload your PDFs and let's get to work.

📚 *What I can do:*
• Summarize your study materials
• Generate 100 practice questions
• Create mock mid & final exams  
• Make flashcards & quizzes
• Predict likely exam questions
• Generate one-night-before summaries

*Get started:* Send me a PDF file or use /upload

Use /help to see all commands."""


HELP_MESSAGE = """📖 *StudyBot AI — Commands*

*📤 Upload & Setup*
/upload — Upload study materials (just send a PDF!)
/status — View your uploaded materials
/reset — Clear all your data and start fresh

*📝 Study Tools*
/summary — Comprehensive topic summary
/questions — Generate 100 practice questions
/notes — Quick short notes for revision

*🧪 Exam Prep*
/mockexam — Generate a mock mid exam
/finalexam — Generate a mock final exam
/predict — Predict likely exam questions
/important — Most important concepts

*⚡ Active Learning*
/quiz — Start an interactive quiz
/flashcards — Study with flashcards

*🌙 Emergency*
/onenighter — One-night-before-exam summary

💡 *Pro tip:* Upload your previous exam papers along with your notes — the bot will detect repeated topics and prioritize them!"""
