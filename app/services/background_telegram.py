import asyncio
import logging
from typing import Optional
from telegram import Bot
from telegram.error import TelegramError
from app.config import TELEGRAM_BOT_API_KEY
from app.services.firestore_db import get_user_chat_id

logger = logging.getLogger(__name__)

class BackgroundTelegramMessenger:
    """Send Telegram messages in background without update context."""
    
    def __init__(self):
        self.bot = Bot(token=TELEGRAM_BOT_API_KEY)
        self.thinking_messages = {}  # Store message IDs for editing
    
    async def send_thinking_message(self, user_id: str, message: str) -> Optional[int]:
        """Send thinking message to user via their chat ID."""
        chat_id = get_user_chat_id(user_id)
        if not chat_id:
            logger.warning(f"No chat ID found for user {user_id}")
            return None
        
        try:
            sent_message = await self.bot.send_message(
                chat_id=chat_id,
                text=f"_{message}_",
                parse_mode='Markdown'
            )
            
            # Store message ID for this user
            self.thinking_messages[user_id] = sent_message.message_id
            logger.info(f"Background thinking message sent to user {user_id}: {message}")
            return sent_message.message_id
            
        except TelegramError as e:
            logger.error(f"Failed to send background message to user {user_id}: {e}")
            return None
    
    async def update_thinking_message(self, user_id: str, new_message: str):
        """Update existing thinking message."""
        chat_id = get_user_chat_id(user_id)
        message_id = self.thinking_messages.get(user_id)
        
        if not chat_id or not message_id:
            logger.warning(f"Cannot update thinking message for user {user_id} - missing chat_id or message_id")
            return
        
        try:
            await self.bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=f"_{new_message}_",
                parse_mode='Markdown'
            )
            logger.info(f"Background thinking message updated for user {user_id}: {new_message}")
            
        except TelegramError as e:
            logger.error(f"Failed to update background message for user {user_id}: {e}")
    
    async def delete_thinking_message(self, user_id: str):
        """Delete thinking message."""
        chat_id = get_user_chat_id(user_id)
        message_id = self.thinking_messages.get(user_id)
        
        if not chat_id or not message_id:
            return
        
        try:
            await self.bot.delete_message(chat_id=chat_id, message_id=message_id)
            self.thinking_messages.pop(user_id, None)
            logger.info(f"Background thinking message deleted for user {user_id}")
            
        except TelegramError as e:
            logger.error(f"Failed to delete background message for user {user_id}: {e}")
    
    async def send_final_message(self, user_id: str, message: str):
        """Send final result message."""
        chat_id = get_user_chat_id(user_id)
        if not chat_id:
            return
        
        try:
            await self.bot.send_message(chat_id=chat_id, text=message)
            logger.info(f"Final message sent to user {user_id}: {message}")
            
        except TelegramError as e:
            logger.error(f"Failed to send final message to user {user_id}: {e}")

# Global instance
background_messenger = BackgroundTelegramMessenger()