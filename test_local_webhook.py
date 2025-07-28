import asyncio
import json
from telegram import Bot
from app.config import TELEGRAM_BOT_API_KEY
import httpx

async def test_local_webhook():
    """Test webhook locally by polling updates and sending them to local endpoint."""
    bot = Bot(token=TELEGRAM_BOT_API_KEY)
    
    # Remove webhook first (so we can use getUpdates)
    await bot.delete_webhook()
    print("Webhook deleted, now using polling for local testing")
    
    last_update_id = 0
    
    while True:
        try:
            # Get updates from Telegram
            updates = await bot.get_updates(offset=last_update_id + 1, timeout=30)
            
            for update in updates:
                last_update_id = update.update_id
                
                # Convert update to JSON
                update_json = update.to_dict()
                
                # Send to local webhook endpoint
                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        "http://localhost:8080/webhook/telegram",
                        json=update_json,
                        headers={"Content-Type": "application/json"}
                    )
                    print(f"Sent update {update.update_id} to local webhook: {response.status_code}")
                    
        except Exception as e:
            print(f"Error: {e}")
            await asyncio.sleep(5)

if __name__ == "__main__":
    asyncio.run(test_local_webhook())