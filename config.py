import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
# For Telegram Stars (XTR), provider token is usually empty or not required in the same way.
# We keep it allow-empty for XTR.
PROVIDER_TOKEN = os.getenv("PROVIDER_TOKEN", "") 
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:password@localhost/bot_db")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "")
WEBHOOK_PATH = "/webhook"
WEBHOOK_PORT = int(os.getenv("PORT", 8443))
ADMIN_ID = int(os.getenv("ADMIN_ID", 0))

# Currency setup
CURRENCY = "XTR"  # Telegram Stars

WATERMARK = "\n\n@LunoViewBot"
