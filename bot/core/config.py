import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")
RAG_API_URL = os.getenv("RAG_API_URL")
SUPER_ADMIN_TELEGRAM_ID = os.getenv("ADMIN_ID")