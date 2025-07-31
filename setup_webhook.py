import asyncio
import os
from telegram import Bot
import dotenv

dotenv.load_dotenv()


async def setup_webhook():
    bot_token = os.getenv("TELEGRAM_BOT_API_KEY")
    webhook_url = os.getenv("WEBHOOK_URL")  
    
    bot = Bot(token=bot_token)
    
    try:
        # Tell Telegram to send updates to your Cloud Run app
        await bot.set_webhook(url=webhook_url)
        print(f"✅ Webhook set to: {webhook_url}")
        
        # Verify it worked
        webhook_info = await bot.get_webhook_info()
        print(f"Current webhook: {webhook_info.url}")
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        await bot.close()

if __name__ == "__main__":
    asyncio.run(setup_webhook())