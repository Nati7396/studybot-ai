import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

UPLOAD_DIR = "bot/uploads"
VECTORSTORE_DIR = "bot/vectorstore"
DATABASE_PATH = "bot/database/studybot.db"

MAX_FILE_SIZE_MB = 50
MAX_CHUNK_SIZE = 1500
CHUNK_OVERLAP = 200

SUPPORTED_EXTENSIONS = [".pdf"]
