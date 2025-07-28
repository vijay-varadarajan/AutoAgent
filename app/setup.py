import asyncio
import os
from telegram import Bot
from app.config import TELEGRAM_BOT_API_KEY

async def setup_webhook():
    """Set up Telegram webhook for Cloud Run deployment."""
    bot = Bot(token=TELEGRAM_BOT_API_KEY)
    
    # Your Cloud Run URL - update this with your actual deployment URL
    # For local testing, you can set a default localhost URL or use a tunneling service like ngrok
    webhook_url = os.environ.get("WEBHOOK_URL", "http://localhost:8000/webhook/telegram")
    
    try:
        # Set webhook
        await bot.set_webhook(url=webhook_url)
        print(f"Webhook set successfully to: {webhook_url}")
        
        # Verify webhook
        webhook_info = await bot.get_webhook_info()
        print(f"Current webhook URL: {webhook_info.url}")
        print(f"Pending updates: {webhook_info.pending_update_count}")
        
    except Exception as e:
        print(f"Error setting webhook: {e}")
    finally:
        await bot.close()

if __name__ == "__main__":
    asyncio.run(setup_webhook())