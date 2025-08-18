from app.services.gemini_responder import send_gemini_response
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters

from app.config import TELEGRAM_BOT_API_KEY
from app.services.rag_service import rag_service
from app.services.rag_state import rag_state


thinking_messages = {}

async def send_thinking_message(update: Update, message: str) -> int:
    """Send a thinking message in italics and return message ID."""
    print(f"Executing function send_thinking_message from c:\\Users\\vijay\\Documents\\Agentic AI\\AutoAgent\\app\\services\\telegram_bot.py:44")
    try:
        sent_message = await update.message.reply_text(
            f"_{message}_",
            parse_mode='Markdown'
        )
        return sent_message.message_id
    except Exception as e:
        print(f"📱 TELEGRAM BOT: ❌ Error sending thinking message: {e}")
        return None


async def edit_thinking_message(update: Update, message_id: int, new_message: str):
    """Edit an existing thinking message."""
    print(f"Executing function edit_thinking_message from c:\\Users\\vijay\\Documents\\Agentic AI\\AutoAgent\\app\\services\\telegram_bot.py:57")
    try:
        await update.get_bot().edit_message_text(
            chat_id=update.effective_chat.id,
            message_id=message_id,
            text=f"_{new_message}_",
            parse_mode='Markdown'
        )
    except Exception as e:
        print(f"📱 TELEGRAM BOT: ❌ Error editing thinking message: {e}")


async def delete_thinking_message(update: Update, message_id: int):
    """Delete a thinking message."""
    print(f"Executing function delete_thinking_message from c:\\Users\\vijay\\Documents\\Agentic AI\\AutoAgent\\app\\services\\telegram_bot.py:70")
    try:
        await update.get_bot().delete_message(
            chat_id=update.effective_chat.id,
            message_id=message_id
        )
    except Exception as e:
        print(f"📱 TELEGRAM BOT: ❌ Error deleting thinking message: {e}")
    
async def rag_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle RAG command to load website and enable RAG mode."""
    user_id = str(update.effective_user.id)
    
    if update.message and update.message.text:
        command_parts = update.message.text.strip().split()
        
        # Check if it's just "/rag" without URL
        if len(command_parts) == 1:
            if rag_state.is_rag_enabled(user_id):
                # Clear user's RAG data and disable
                rag_service.clear_user_data(user_id)
                rag_state.disable_rag_for_user(user_id)
                await update.message.reply_text("🔴 RAG mode disabled. Your data has been cleared. Back to normal AutoAgent mode.")
            else:
                await update.message.reply_text("Please provide a URL: `/rag https://example.com`")
            return
        
        # Extract URL from command
        urls = command_parts[1:] if len(command_parts) > 1 else ""

        for url in urls:
            if not url.startswith("http"):
                await update.message.reply_text(f"This URL: {url} is invalid. Please provide a valid URL: `/rag https://example.com`")
                return

        # Send loading message
        loading_msg = await update.message.reply_text("🔄 _Loading and indexing website content..._", parse_mode='Markdown')
        
        try:
            # Load the website into RAG for this specific user
            result = await rag_service.load_website(user_id, urls)
            
            print("Loaded website. Enabling RAG mode...")
            # Enable RAG mode for this user
            rag_state.enable_rag_for_user(user_id, urls)
            
            # Update the loading message
            await loading_msg.edit_text(
                f"✅ {result}\n\n"
                f"🟢 RAG mode enabled! All your messages will now query this website content.\n"
                f"Your personal collection: `user_{user_id}_rag`\n"
                f"Send `/rag` again to disable RAG mode and clear your data."
            )
            
        except Exception as e:
            await loading_msg.edit_text(f"❌ Error loading website: {str(e)}")
    
    else:
        await update.message.reply_text("Please provide a URL: `/rag https://example.com`")


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start command - minimal welcome message."""
    user_id = str(update.effective_user.id)
    username = update.effective_user.username or update.effective_user.first_name or "User"
    
    welcome_message = f"""
🤖 **Welcome to RAGAgent, {username}!**

I'm your intelligent RAG agent that can:
• 📧 Converse with you
• 🔗 Learn info from websites and answer your questions

Send `/help` to see all available commands and features.

**Quick start:** Try saying "/rag https://example.com" to load a website and ask questions about it!
"""
    
    await update.message.reply_text(welcome_message, parse_mode='Markdown')


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /help command - detailed functionality overview."""

    help_message = """
🤖 **RAGAgent - Complete Feature Guide**

**🔗 Smart Website RAG (Retrieval-Augmented Generation)**
• Load any website: `/rag https://example.com`
• Ask questions about the loaded content
• Support multiple URLs: `/rag https://site1.com https://site2.com`
• Disable RAG mode: `/rag` (without URL)

**💬 Natural Language Processing**
• Type requests naturally - no complex syntax needed
• Automatic mode switching (conversation vs rag agent)
• Context-aware responses for RAG agent.

**⚙️ Available Commands**
• `/start` - Welcome message
• `/help` - This detailed guide
• `/rag <url>` - Enable website Q&A mode
• `[No command] <conversation>` - Start a conversation with RAGAgent
"""
    
    await update.message.reply_text(help_message, parse_mode='Markdown')


async def conversation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle user commands and process workflows. Also handle photo uploads."""
    print(f"Executing function conversation from c:\\Users\\vijay\\Documents\\Agentic AI\\AutoAgent\\app\\services\\telegram_bot.py:347")
    user_id = str(update.effective_user.id)
    chat_id = update.effective_chat.id
    username = update.effective_user.username
    
    prompt = update.message.text.strip() if update.message and update.message.text else ""
    
    print("Prompt:", prompt)
    
    if not prompt:
        await update.message.reply_text("Please provide an action, e.g. 'Send email to <recipient> with subject <subject> and body <body>'.")
        return
    
    print(f"Prompt: {prompt}, is rag enabled: {rag_state.is_rag_enabled(user_id)}")
    
    # CHECK: If RAG is enabled for this user, route to RAG service
    if rag_state.is_rag_enabled(user_id):
        try:
            # Send thinking message
            thinking_msg = await update.message.reply_text("🤔 _Searching your website content..._", parse_mode='Markdown')
            
            # Query RAG service with user_id
            rag_response = await rag_service.query(user_id, prompt)
            print("Rag response", rag_response)
            
            # Delete thinking message and send response
            await thinking_msg.delete()
            await update.message.reply_text(f"🔍 **RAG Response:**\n\n{rag_response}", parse_mode='Markdown')
            return
            
        except Exception as e:
            print(f"📱 TELEGRAM BOT: ❌ Error processing RAG query: {e}")
            return
        
    else:
        print("Sending Gemini response...")
        await send_gemini_response(update, prompt)
        return


def run_bot() -> None:
    """Initialize and run the Telegram bot."""
    print(f"Executing function run_bot from c:\\Users\\vijay\\Documents\\Agentic AI\\AutoAgent\\app\\services\\telegram_bot.py:412")
    app = ApplicationBuilder().token(TELEGRAM_BOT_API_KEY).build()
    
    # Add handlers
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("rag", rag_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, conversation))
    
    app.run_polling()


if __name__ == "__main__":
    run_bot()