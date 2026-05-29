import os
import logging
from telegram import Update
from telegram.ext import ContextTypes
from bot.config import MAX_FILE_SIZE_MB, SUPPORTED_EXTENSIONS
from bot.database.db import upsert_user, add_document
from bot.services.pdf_service import extract_text_from_pdf, split_into_chunks, save_uploaded_file
from bot.services.vector_service import add_chunks_to_index

logger = logging.getLogger(__name__)

MAX_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024


async def upload_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📤 *Ready to receive your study materials!*\n\n"
        "Just send me a PDF file directly in this chat.\n\n"
        "You can upload:\n"
        "• Lecture notes & slides\n"
        "• Previous exam papers\n"
        "• Textbook chapters\n"
        "• Short notes & handouts\n\n"
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
            f"⚠️ Sorry, I only support PDF files right now.\n"
            f"You sent: `{ext}` file",
            parse_mode="Markdown"
        )
        return

    if doc.file_size and doc.file_size > MAX_BYTES:
        await update.message.reply_text(
            f"⚠️ File too large! Maximum size is {MAX_FILE_SIZE_MB}MB.\n"
            f"Your file: {doc.file_size / (1024*1024):.1f}MB"
        )
        return

    status_msg = await update.message.reply_text(
        f"📥 Receiving *{file_name}*...\n⏳ Please wait while I process it.",
        parse_mode="Markdown"
    )

    try:
        tg_file = await context.bot.get_file(doc.file_id)
        file_bytes = await tg_file.download_as_bytearray()

        await status_msg.edit_text(
            f"📖 Reading *{file_name}*...\n⏳ Extracting text from PDF...",
            parse_mode="Markdown"
        )

        file_path = save_uploaded_file(user.id, bytes(file_bytes), file_name)

        text, page_count = extract_text_from_pdf(file_path)

        if not text or len(text) < 50:
            await status_msg.edit_text(
                "⚠️ Couldn't extract text from this PDF. It might be scanned or image-based.\n"
                "Try a PDF with selectable text."
            )
            return

        await status_msg.edit_text(
            f"🧠 *Processing {page_count} pages*...\n⏳ Building your study index...",
            parse_mode="Markdown"
        )

        chunks = split_into_chunks(text)
        add_chunks_to_index(user.id, chunks)

        add_document(
            user_id=user.id,
            filename=os.path.basename(file_path),
            original_name=file_name,
            file_type="pdf",
            page_count=page_count,
            char_count=len(text)
        )

        await status_msg.edit_text(
            f"✅ *{file_name}* processed successfully!\n\n"
            f"📄 Pages: {page_count}\n"
            f"📝 Text extracted: {len(text):,} characters\n"
            f"🧩 Study chunks: {len(chunks)}\n\n"
            f"You can now use:\n"
            f"/summary — Get a summary\n"
            f"/questions — Generate 100 questions\n"
            f"/quiz — Start a quiz\n"
            f"/mockexam — Create a mock exam",
            parse_mode="Markdown"
        )

    except Exception as e:
        logger.error(f"Upload error for user {user.id}: {e}", exc_info=True)
        await status_msg.edit_text(
            f"❌ Error processing file: {str(e)[:200]}\n\nPlease try again."
        )
