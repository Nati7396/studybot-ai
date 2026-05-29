import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")

# Multi-key support: GEMINI_API_KEY, GEMINI_API_KEY_2, GEMINI_API_KEY_3, etc.
def _load_gemini_keys() -> list[str]:
    keys = []
    primary = os.getenv("GEMINI_API_KEY", "").strip()
    if primary:
        keys.append(primary)
    for i in range(2, 10):
        k = os.getenv(f"GEMINI_API_KEY_{i}", "").strip()
        if k:
            keys.append(k)
    return keys

GEMINI_API_KEYS = _load_gemini_keys()
GEMINI_API_KEY = GEMINI_API_KEYS[0] if GEMINI_API_KEYS else ""

UPLOAD_DIR = "bot/uploads"
VECTORSTORE_DIR = "bot/vectorstore"
DATABASE_PATH = "bot/database/studybot.db"

# Telegram bots can only download files up to 20MB via Bot API
# Files above this size will fail at the Telegram download step
MAX_FILE_SIZE_MB = 20
MAX_CHUNK_SIZE = 1500
CHUNK_OVERLAP = 200

SUPPORTED_EXTENSIONS = [".pdf", ".pptx", ".ppt", ".docx", ".doc", ".txt"]
