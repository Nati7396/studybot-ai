import logging
from telegram import Update
from telegram.ext import ContextTypes
from bot.database.db import upsert_user
from bot.utils.helpers import WELCOME_MESSAGE, HELP_MESSAGE

logger = logging.getLogger(__name__)


async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    upsert_user(user.id, user.username or "", user.first_name or "")
    await update.message.reply_text(WELCOME_MESSAGE, parse_mode="Markdown")


async def help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(HELP_MESSAGE, parse_mode="Markdown")
