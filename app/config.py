import os, json
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_API_KEY = os.getenv("TELEGRAM_BOT_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")