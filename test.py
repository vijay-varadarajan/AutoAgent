# Quick check script
import asyncio
from telegram import Bot
import os
import dotenv

dotenv.load_dotenv()

async def check_webhook():
    bot = Bot(token=os.getenv("TELEGRAM_BOT_API_KEY"))
    info = await bot.get_webhook_info()
    print(f"Webhook URL: {info.url}")
    print(f"Pending updates: {info.pending_update_count}")
    if info.last_error_date:
        print(f"Last error: {info.last_error_message}")
    await bot.close()

asyncio.run(check_webhook())