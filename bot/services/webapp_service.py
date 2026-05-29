import os
import json
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

WEBAPP_DIR = "bot/webapp_data"


def save_webapp_data(user_id: int, key: str, value):
    os.makedirs(WEBAPP_DIR, exist_ok=True)
    path = os.path.join(WEBAPP_DIR, f"{user_id}.json")

    data = {}
    if os.path.exists(path):
        try:
            with open(path, "r") as f:
                data = json.load(f)
        except Exception:
            data = {}

    data[key] = value
    data["updated_at"] = datetime.utcnow().isoformat()
    data["user_id"] = user_id

    with open(path, "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    logger.info(f"Saved webapp data for user {user_id}: {key}")


def get_webapp_data(user_id: int) -> dict:
    path = os.path.join(WEBAPP_DIR, f"{user_id}.json")
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r") as f:
            return json.load(f)
    except Exception:
        return {}
