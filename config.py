import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN not found")

SENIOR_ADMIN_IDS = []
admin_ids = os.getenv("SENIOR_ADMIN_IDS", "")
if admin_ids:
    SENIOR_ADMIN_IDS = [int(id.strip()) for id in admin_ids.split(",") if id.strip()]

SPAM_THRESHOLD = int(os.getenv("SPAM_THRESHOLD", "2"))
MUTE_DURATION = int(os.getenv("MUTE_DURATION", "300"))
STICKER_SPAM_THRESHOLD = int(os.getenv("STICKER_SPAM_THRESHOLD", "3"))
STICKER_TIME_WINDOW = int(os.getenv("STICKER_TIME_WINDOW", "10"))
DEBUG = os.getenv("DEBUG", "False").lower() == "true"
DATABASE_PATH = os.getenv("DATABASE_PATH", "bot_database.db")
DEFAULT_MUTE_TIME = int(os.getenv("DEFAULT_MUTE_TIME", "3600"))

LEVELS = {
    1: "👤 Обычный пользователь",
    2: "💰 Донатер",
    3: "🛡️ Младший модератор",
    4: "🛡️ Модератор",
    5: "👑 Младший админ",
    6: "👑 Старший админ"
}
