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

I help you study smarter from your own materials. Upload your files and let's get to work.

📚 *What I can do:*
• Summarize your study materials
• Generate practice questions & quizzes
• Create mock mid & final exams
• Make flashcards & short notes
• Predict likely exam questions
• One-night-before emergency summaries
• Analyze your professor's exam style

📁 *Supported files:* PDF, PowerPoint, Word, TXT

*Get started:* Send me a file or use /upload
Use /help to see all commands.

─────────────────────
🤖 Created by *@Nati7396*
💬 Questions or feedback? Contact @Nati7396"""


HELP_MESSAGE = """📖 *StudyBot AI — All Commands*

*📤 Upload & Manage*
/upload — How to upload study materials
/focus — Set chapter/section focus for all commands
/status — Your uploaded files, AI key status & current focus
/reset — Clear all your data and start fresh

*📝 Study Tools*
/summary — Comprehensive topic summary
/questions — Generate practice questions
/notes — Quick short notes for revision
/important — Most important exam concepts

*🧪 Exam Prep*
/mockexam — Mock mid exam paper
/finalexam — Mock final exam paper
/predict — Predict likely exam questions
/examstyle — Generate questions in your professor's exact style

*⚡ Active Learning*
/quiz — Interactive scored quiz (10/20/30/50 Qs)
/flashcards — Study with flip flashcards

*🌙 Emergency Mode*
/onenighter — One-night-before-exam survival guide

*🔍 Other*
/explain [topic] — Explain any concept simply
/app — Open the Study App

─────────────────────
✅ *Supported file types:* PDF, PPTX, DOCX, TXT
📦 *Max file size:* 20MB (Telegram limit)

💡 *Pro tip:* Upload your previous exam papers — the bot learns your professor's question style!

─────────────────────
🤖 Created by *@Nati7396* | Contact for support"""
