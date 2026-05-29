import os
import logging
from telegram import Update
from telegram.ext import ContextTypes
from bot.config import MAX_FILE_SIZE_MB, SUPPORTED_EXTENSIONS
from bot.database.db import upsert_user, add_document
from bot.services.pdf_service import extract_text_from_file, split_into_chunks, save_uploaded_file
from bot.services.vector_service import add_chunks_to_index

logger = logging.getLogger(__name__)

MAX_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024

SUPPORTED_DISPLAY = "PDF, PPTX, DOCX, TXT"

TYPE_EMOJI = {
    ".pdf": "📄",
    ".pptx": "📊",
    ".ppt": "📊",
    ".docx": "📝",
    ".doc": "📝",
    ".txt": "📃",
}


async def upload_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📤 *Ready to receive your study materials!*\n\n"
        "Just send me a file directly in this chat.\n\n"
        "✅ *Supported formats:*\n"
        "• 📄 PDF — lecture notes, exams, textbooks\n"
        "• 📊 PowerPoint (.pptx) — slide decks\n"
        "• 📝 Word (.docx) — documents & essays\n"
        "• 📃 Text (.txt) — plain notes\n\n"
        "📦 *Max size:* 20MB per file (Telegram limit)\n\n"
        "The more you upload, the smarter I get! 📚",
        parse_mode="Markdown"
    )


async def document_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    upsert_user(user.id, user.username or "", user.first_name or "")

    doc = update.message.document
    if not doc:
        return

    file_name = doc.file_name or "unknown.pdf"
    _, ext = os.path.splitext(file_name.lower())

    if ext not in SUPPORTED_EXTENSIONS:
        await update.message.reply_text(
            f"⚠️ *Unsupported file type:* `{ext}`\n\n"
            f"✅ I support: *{SUPPORTED_DISPLAY}*\n\n"
            f"For PowerPoint: save as `.pptx`\n"
            f"For Word: save as `.docx`\n"
            f"For scanned files: convert to PDF first",
            parse_mode="Markdown"
        )
        return

    if doc.file_size and doc.file_size > MAX_BYTES:
        size_mb = doc.file_size / (1024 * 1024)
        await update.message.reply_text(
            f"⚠️ *File too large!*\n\n"
            f"Your file: *{size_mb:.1f}MB*\n"
            f"Telegram limit for bots: *{MAX_FILE_SIZE_MB}MB*\n\n"
            f"💡 *Tips to reduce size:*\n"
            f"• Compress the PDF (use smallpdf.com)\n"
            f"• Split it into chapters and upload separately\n"
            f"• Remove images if they're not essential",
            parse_mode="Markdown"
        )
        return

    emoji = TYPE_EMOJI.get(ext, "📁")
    status_msg = await update.message.reply_text(
        f"{emoji} Receiving *{file_name}*...\n⏳ Please wait while I process it.",
        parse_mode="Markdown"
    )

    try:
        tg_file = await context.bot.get_file(doc.file_id)
        file_bytes = await tg_file.download_as_bytearray()

        type_label = {
            ".pdf": "PDF", ".pptx": "PowerPoint", ".ppt": "PowerPoint",
            ".docx": "Word document", ".doc": "Word document", ".txt": "text file"
        }.get(ext, "file")

        await status_msg.edit_text(
            f"{emoji} Reading *{file_name}*...\n⏳ Extracting text from {type_label}...",
            parse_mode="Markdown"
        )

        file_path = save_uploaded_file(user.id, bytes(file_bytes), file_name)
        text, page_count = extract_text_from_file(file_path)

        if not text or len(text) < 50:
            await status_msg.edit_text(
                f"⚠️ *Couldn't extract text from this file.*\n\n"
                f"Possible reasons:\n"
                f"• It's a scanned image with no selectable text\n"
                f"• The file is password-protected\n"
                f"• The file is corrupted\n\n"
                f"💡 Try: export as PDF with selectable text, or retype key content as .txt"
            )
            return

        await status_msg.edit_text(
            f"🧠 *Processing content*...\n⏳ Building your study index...",
            parse_mode="Markdown"
        )

        chunks = split_into_chunks(text)
        add_chunks_to_index(user.id, chunks)

        pages_label = f"{page_count} pages" if page_count > 1 else (
            f"{page_count} slides" if ext in (".pptx", ".ppt") else "1 page"
        )

        add_document(
            user_id=user.id,
            filename=os.path.basename(file_path),
            original_name=file_name,
            file_type=ext.lstrip("."),
            page_count=page_count,
            char_count=len(text)
        )

        await status_msg.edit_text(
            f"✅ *{file_name}* processed!\n\n"
            f"{emoji} Type: {type_label}\n"
            f"📄 {pages_label}\n"
            f"📝 Text extracted: {len(text):,} characters\n"
            f"🧩 Study chunks: {len(chunks)}\n\n"
            f"Ready! Use:\n"
            f"/summary — Get a summary\n"
            f"/questions — Generate practice questions\n"
            f"/quiz — Start a quiz\n"
            f"/mockexam — Create a mock exam",
            parse_mode="Markdown"
        )

    except Exception as e:
        err = str(e)
        logger.error(f"Upload error for user {user.id}: {e}", exc_info=True)
        if "file is too big" in err.lower() or "file_size" in err.lower():
            await status_msg.edit_text(
                f"⚠️ *Telegram couldn't deliver this file.*\n\n"
                f"Telegram limits bot downloads to {MAX_FILE_SIZE_MB}MB.\n"
                f"Please compress the file or split it into smaller parts."
            )
        else:
            await status_msg.edit_text(
                f"❌ Error processing file: {err[:200]}\n\nPlease try again."
            )
