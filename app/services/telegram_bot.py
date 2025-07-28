import json
import logging
import os
from typing import List, Optional, Set, Dict, Any
from urllib.parse import urlencode

import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters

from app.services.gemini_parser import send_gemini_response
from app.config import TELEGRAM_BOT_API_KEY, GOOGLE_CLIENT_ID
from app.services.firestore_db import get_google_tokens, save_photo, save_user_chat_info, clear_google_tokens
from app.services.enhanced_workflow_executor import EnhancedWorkflowExecutor
from app.logging_config import setup_logging  # Import centralized logging
from app.services.rag_service import rag_service
from app.services.rag_state import rag_state

# Get logger (centralized logging already configured)
logger = logging.getLogger(__name__)

# Constants
BACKEND_URL = f"{os.getenv('BACKEND_URL')}"
REDIRECT_URI = f"{os.getenv('REDIRECT_URI')}"

# Store for thinking messages (in production, use Redis or database)
thinking_messages = {}

# Google OAuth scope mappings
GOOGLE_ACTION_SCOPES = {
    "email_send": "https://www.googleapis.com/auth/gmail.send https://www.googleapis.com/auth/gmail.compose",
    "email_read": "https://www.googleapis.com/auth/gmail.readonly",
    "email": "https://www.googleapis.com/auth/gmail.send https://www.googleapis.com/auth/gmail.readonly https://www.googleapis.com/auth/gmail.compose https://www.googleapis.com/auth/gmail.modify"
    # "calendar": "https://www.googleapis.com/auth/calendar",
    # "drive": "https://www.googleapis.com/auth/drive",
    # "photos": "https://www.googleapis.com/auth/photoslibrary",
    # "meet": "https://www.googleapis.com/auth/meetings.space.created",
    # "sheets": "https://www.googleapis.com/auth/spreadsheets",
    # "docs": "https://www.googleapis.com/auth/documents",
    # "slides": "https://www.googleapis.com/auth/presentations",
}

# Action to scope mapping for workflow tasks
ACTION_SCOPE_MAP = {
    "email": "email",
    # "calendar_event": "calendar",
    # "drive_upload": "drive",
    # "spreadsheet": "sheets",
    # "document": "docs",
    # "presentation": "slides",
    # "photo_upload": "photos",
    # "meet": "meet",
}


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
        logger.error(f"📱 TELEGRAM BOT: ❌ Error sending thinking message: {e}")
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
        logger.error(f"📱 TELEGRAM BOT: ❌ Error editing thinking message: {e}")


async def delete_thinking_message(update: Update, message_id: int):
    """Delete a thinking message."""
    print(f"Executing function delete_thinking_message from c:\\Users\\vijay\\Documents\\Agentic AI\\AutoAgent\\app\\services\\telegram_bot.py:70")
    try:
        await update.get_bot().delete_message(
            chat_id=update.effective_chat.id,
            message_id=message_id
        )
    except Exception as e:
        logger.error(f"📱 TELEGRAM BOT: ❌ Error deleting thinking message: {e}")


def get_google_auth_url(user_id: str, scopes: Optional[List[str]] = None) -> str:
    """Generate Google OAuth authorization URL."""
    print(f"Executing function get_google_auth_url from c:\\Users\\vijay\\Documents\\Agentic AI\\AutoAgent\\app\\services\\telegram_bot.py:90")
    if scopes is None:
        scopes = list(GOOGLE_ACTION_SCOPES.values())
    
    params = {
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": " ".join(scopes),
        "access_type": "offline",
        "state": user_id,
        "prompt": "consent",
    }
    return f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}"


def parse_workflow_json(workflow: Any) -> Dict[str, Any]:
    """Parse workflow data, handling both string and dict formats."""
    print(f"Executing function parse_workflow_json from c:\\Users\\vijay\\Documents\\Agentic AI\\AutoAgent\\app\\services\\telegram_bot.py:109")
    if isinstance(workflow, dict):
        return workflow
    
    if isinstance(workflow, str):
        try:
            # Remove markdown code block markers if present
            cleaned_workflow = workflow.strip()
            if cleaned_workflow.startswith('```'):
                lines = cleaned_workflow.strip('`').split('\n')
                # Remove language tag if present (e.g., ```json)
                if lines and not lines[0].strip().startswith('{'):
                    lines = lines[1:]
                cleaned_workflow = '\n'.join(lines)
            
            return json.loads(cleaned_workflow)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse workflow JSON: {e}")
            return {}
    
    return {}


def extract_required_scopes_from_workflow(workflow: Any) -> Set[str]:
    """Extract required Google OAuth scopes from workflow tasks."""
    print(f"Executing function extract_required_scopes_from_workflow from c:\\Users\\vijay\\Documents\\Agentic AI\\AutoAgent\\app\\services\\telegram_bot.py:94")
    
    parsed_workflow = parse_workflow_json(workflow)
    if not parsed_workflow:
        return set()
    
    required_scopes = set()
    tasks = parsed_workflow.get("tasks", [])
    
    for task in tasks:
        action = task.get("action")
        mode = task.get("mode", "send")  # Default to send mode
        
        if action == "email":
            if mode == "read":
                scope_key = "email_read"
            elif mode == "send":
                scope_key = "email_send" 
            else:
                scope_key = "email"  # Fallback to all email scopes
                
            scope_string = GOOGLE_ACTION_SCOPES.get(scope_key, "")
            if scope_string:
                required_scopes.update(scope_string.split())
    
    return required_scopes

def get_missing_scopes(user_id: str, required_scopes: Set[str]) -> Set[str]:
    """Determine which scopes are missing for a user."""
    print(f"Executing function get_missing_scopes from c:\\Users\\vijay\\Documents\\Agentic AI\\AutoAgent\\app\\services\\telegram_bot.py:152")
    tokens = get_google_tokens(user_id)
    
    if not tokens or 'scope' not in tokens:
        return set(required_scopes)
    
    granted_scopes = set(tokens['scope'])
    missing_scopes = set(required_scopes) - granted_scopes
    
    return missing_scopes


async def send_auth_prompt(update: Update, user_id: str, missing_scopes: List[str]) -> None:
    """Send authorization prompt with inline keyboard."""
    print(f"Executing function send_auth_prompt from c:\\Users\\vijay\\Documents\\Agentic AI\\AutoAgent\\app\\services\\telegram_bot.py:164")
    auth_url = get_google_auth_url(user_id, missing_scopes)
    keyboard = [[InlineKeyboardButton("Connect Google services for this workflow", url=auth_url)]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "To enable this workflow, please connect the required Google services:",
        reply_markup=reply_markup
    )


async def execute_workflow_with_thinking(update: Update, workflow_id: str):
    """Execute workflow and show thinking process."""
    print(f"Executing function execute_workflow_with_thinking from c:\\Users\\vijay\\Documents\\Agentic AI\\AutoAgent\\app\\services\\telegram_bot.py:176")
    thinking_id = None
    
    try:
        # Send initial thinking message
        # thinking_id = await send_thinking_message(update, "🤔 Preparing to execute workflow...")
        
        # Store thinking message ID
        user_id = str(update.effective_user.id)
        # thinking_messages[user_id] = thinking_id
        
        # Execute workflow
        executor = EnhancedWorkflowExecutor(workflow_id, update)
        
        # Load workflow
        if not executor.load_workflow():
            await update.message.reply_text("❌ Failed to load workflow")
            return
        
        # Execute workflow with thinking process
        success, final_result = await executor.execute_workflow()

        # Create result dict for compatibility
        if success:
            # If final_result is a string, try to parse it as JSON
            if isinstance(final_result, str):
                try:
                    final_result = json.loads(final_result)
                except Exception as e:
                    logger.error(f"Failed to parse final_result as JSON: {e}")
            result = {"status": "completed", "results": final_result}
        else:
            result = {"status": "failed", "error": "Workflow execution failed"}
        
        # Clean up thinking message
        # if thinking_id:
        #     await delete_thinking_message(update, thinking_id)
        
        # Send final result
        if result.get("status") == "completed":
            
            # Send results summary
            results = result.get("results", {})
            if results:
                print(f"FINAL RESULTS: type = {type(results)} {results}")
                for res in results['execution_results']:
                    summary = "\n".join([f"{line}" for line in res['result'].split('\n') ])
                await update.message.reply_text(f"📊 Results:\n{summary}")
                
        elif result.get("status") == "failed":
            error_msg = result.get("error", "Unknown error")
            await update.message.reply_text(f"❌ Workflow failed: {error_msg}")
        else:
            await update.message.reply_text(f"⚠️ Workflow status: {result.get('status', 'Unknown')}")
            
    except Exception as e:
        logger.error(f"Error executing workflow: {e}")
        # if thinking_id:
        #     await delete_thinking_message(update, thinking_id)
        await update.message.reply_text(f"💥 Error executing workflow: {str(e)}")
    finally:
        # Clean up thinking messages store
        user_id = str(update.effective_user.id)
        thinking_messages.pop(user_id, None)


def validate_workflow(workflow: Any) -> Optional[str]:
    """Validate email workflow has required fields for both read and write modes. Returns error message if validation fails."""
    print(f"Executing function validate_workflow from c:\\Users\\vijay\\Documents\\Agentic AI\\AutoAgent\\app\\services\\telegram_bot.py:233")
    parsed_workflow = parse_workflow_json(workflow)
    print(f"Parsed workflow: {parsed_workflow}")
    if not parsed_workflow:
        return None
    
    missing_fields = []
    tasks = parsed_workflow.get("tasks", [])
    conversations = [task for task in tasks if task.get('action') == 'conversation']

    print(f"Conversations found: {conversations}")
    if conversations:
        return False, "not_workflow"  # Special flag for non-workflow messages
    
    # Define placeholder values that should be treated as missing
    placeholder_patterns = {
        'recipient': [' ', 'recipient@example.com', 'email@example.com', 'user@example.com', 'example@email.com'],
        'subject': [' ', 'Subject', 'Email subject', 'Email Subject', 'subject', 'SUBJECT'],
        'query': [' ', 'query', 'search query', 'Search Query', 'QUERY', 'search']
    }
    
    for i, task in enumerate(tasks):
        if task.get('action') == 'email':
            task_missing = []
            mode = task.get('mode', 'write')  # Default to write mode for backward compatibility
            
            if mode == 'read':
                # For read mode, only query is required
                query = str(task.get('query', '')).strip()
                if not query or query in placeholder_patterns['query']:
                    task_missing.append('query')
            else:
                # For write mode (send email), recipient and subject are required
                recipient = str(task.get('recipient', '')).strip()
                if not recipient or recipient in placeholder_patterns['recipient']:
                    task_missing.append('recipient')
                
                subject = str(task.get('subject', '')).strip()
                if not subject or subject in placeholder_patterns['subject']:
                    task_missing.append('subject')
            
            if task_missing:
                missing_fields.extend(task_missing)
    
    if missing_fields:
        # Remove duplicates while preserving order
        unique_missing = []
        seen = set()
        for field in missing_fields:
            if field not in seen:
                unique_missing.append(field)
                seen.add(field)
        
        if len(unique_missing) == 1:
            return True, f"You have not provided {unique_missing[0]}. Please repeat with all required fields."
        else:
            return True, f"You have not provided {', '.join(unique_missing)}. Please repeat with all required fields."
    
    return True, None



# Store for pending workflows per user (in production, use Redis or database)
pending_workflows_by_user = {}

async def handle_backend_response(update: Update, user_id: str, response: requests.Response, prompt: str) -> None:
    """Handle the backend API response and start workflow execution."""
    print(f"Executing function handle_backend_response from c:\\Users\\vijay\\Documents\\Agentic AI\\AutoAgent\\app\\services\\telegram_bot.py:301")
    try:
        data = response.json()
    except json.JSONDecodeError:
        data = response.text
    
    if not isinstance(data, dict):
        await update.message.reply_text(f"Unexpected backend response: {data}")
        return
    
    workflow_id = data.get('workflow_id', 'unknown')
    
    # Send initial confirmation
    print(f"Workflow ID: {workflow_id}")
    if workflow_id == 'conversation_001':
        await send_gemini_response(update, prompt)
        return
    await update.message.reply_text(f"🎯 Workflow created! ID: {workflow_id}")
    
    workflow = data.get("workflow")
    if not workflow:
        return

    # Validate workflow requirements before proceeding
    is_valid_workflow, validation_error = validate_workflow(workflow)
    if not is_valid_workflow and validation_error == "not_workflow":
        await send_gemini_response(update, prompt)
        return
    elif validation_error:
        logger.error(f"📱 TELEGRAM BOT: Workflow validation failed: {validation_error}")
        await update.message.reply_text(f"❌ {validation_error}")
        return
    
    required_scopes = extract_required_scopes_from_workflow(workflow)
    
    if required_scopes:
        missing_scopes = get_missing_scopes(user_id, required_scopes)
        
        if missing_scopes:
            # Store workflow ID for this user so we can execute it after OAuth
            pending_workflows_by_user[user_id] = workflow_id
            
            await send_auth_prompt(update, user_id, list(missing_scopes))
            await update.message.reply_text("✅ After authorization, your workflow will execute automatically!")
            return
        else:
            await update.message.reply_text("✅ All required Google service permissions are already granted!")
    
    # Start workflow execution with thinking process
    await execute_workflow_with_thinking(update, workflow_id)


async def do_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle user commands and process workflows. Also handle photo uploads."""
    print(f"Executing function do_command from c:\\Users\\vijay\\Documents\\Agentic AI\\AutoAgent\\app\\services\\telegram_bot.py:347")
    user_id = str(update.effective_user.id)
    chat_id = update.effective_chat.id
    username = update.effective_user.username

    save_user_chat_info(user_id, chat_id, username)

    prompt = update.message.text.strip() if update.message and update.message.text else ""

    # Handle photo upload if present
    if update.message and update.message.photo:
        # Get the highest resolution photo
        photo = update.message.photo[-1]
        file_id = photo.file_id
        new_file = await context.bot.get_file(file_id)
        photo_bytes = await new_file.download_as_bytearray()
        # Save photo to Firestore
        save_photo(user_id, photo_bytes, file_id)
        await update.message.reply_text("Photo uploaded and saved to Firestore!")
        # Optionally, continue to process the prompt if present
        if not prompt:
            return

    if not prompt:
        await update.message.reply_text("Please provide an action, e.g. 'Send email to <recipient> with subject <subject> and body <body>'.")
        return
    
    
    # CHECK: If RAG is enabled for this user, route to RAG service
    if rag_state.is_rag_enabled(user_id):
        try:
            # Send thinking message
            thinking_msg = await update.message.reply_text("🤔 _Searching your website content..._", parse_mode='Markdown')
            
            # Query RAG service with user_id
            rag_response = await rag_service.query(user_id, prompt)
            
            # Delete thinking message and send response
            await thinking_msg.delete()
            await update.message.reply_text(f"🔍 **RAG Response:**\n\n{rag_response}", parse_mode='Markdown')
            return
            
        except Exception as e:
            await update.message.reply_text(f"❌ RAG query failed: {str(e)}")
            return
        
    
    payload = {"user_id": user_id, "prompt": prompt}
    
    try:
        response = requests.post(BACKEND_URL, json=payload, timeout=30)
        
        if not response:
            await update.message.reply_text("❌ Wrong format of workflow. Please repeat with all required fields.")
            return
        if response.status_code == 200:
            await handle_backend_response(update, user_id, response, prompt)
        else:
            logger.error(f"📱 TELEGRAM BOT: ❌ Backend error {response.status_code}: {response.text}")
            await update.message.reply_text(f"Error: {response.text}")
            
    except requests.RequestException as e:
        logger.error(f"📱 TELEGRAM BOT: ❌ Backend request failed for user {user_id}: {e}")
        await update.message.reply_text(f"Failed to connect to backend: {e}")


async def connect(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /connect command for Google services authorization."""
    print(f"Executing function connect from c:\\Users\\vijay\\Documents\\Agentic AI\\AutoAgent\\app\\services\\telegram_bot.py:393")
    user_id = str(update.effective_user.id)

    clear_google_tokens(user_id)

    tokens = get_google_tokens(user_id)
    if tokens:
        await update.message.reply_text("Your Google services are already connected!")
        return
    
    # Use all available scopes for direct /connect command
    auth_url = get_google_auth_url(user_id)
    keyboard = [[InlineKeyboardButton("Connect Google services", url=auth_url)]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "To connect your Google services, please click the button below and authorize access:",
        reply_markup=reply_markup
    )
    
    
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
🤖 **Welcome to AutoAgent, {username}!**

I'm your intelligent workflow automation assistant that can:
• 📧 Automate email tasks
• 🔗 Answer questions from websites
• 🔌 Connect with Google services

Send `/help` to see all available commands and features.

**Quick start:** Try saying "Send email to someone@example.com with subject 'Hello' and body 'Hi there!'"
"""
    
    await update.message.reply_text(welcome_message, parse_mode='Markdown')


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /help command - detailed functionality overview."""
    help_message = """
🤖 **AutoAgent - Complete Feature Guide**

**📧 Email Automation**
• Send emails: "Send email to john@example.com with subject 'Meeting' and body 'Let's meet tomorrow'"
• Read emails: "Read emails from boss@company.com about project updates"

**🔗 Smart Website RAG (Retrieval-Augmented Generation)**
• Load any website: `/rag https://example.com`
• Ask questions about the loaded content
• Support multiple URLs: `/rag https://site1.com https://site2.com`
• Disable RAG mode: `/rag` (without URL)

**🔌 Google Services Integration**
• Connect your account: `/connect`
• Automatic permission requests for workflows
• Currently supports: Gmail (send/read)
• Coming soon: Calendar, Drive, Photos, Docs, Sheets

**💬 Natural Language Processing**
• Type requests naturally - no complex syntax needed
• Automatic mode switching (workflow vs conversation)
• Context-aware responses for RAG agent.

**⚙️ Available Commands**
• `/start` - Welcome message
• `/help` - This detailed guide
• `[No command] <action>` - Execute a workflow action
• `/rag <url>` - Enable website Q&A mode
• `/connect` - Link Google services

__Usage Examples__
1. "Send a test email to <recipient> with subject 'Test' and body 'Hello world'"
2. `/rag https://docs.python.org` then ask "What is a list comprehension?"
3. "Read my latest emails from gmail"

Just type naturally - I'll understand and automate it for you! 🎯
"""
    
    await update.message.reply_text(help_message, parse_mode='Markdown')


def run_bot() -> None:
    """Initialize and run the Telegram bot."""
    print(f"Executing function run_bot from c:\\Users\\vijay\\Documents\\Agentic AI\\AutoAgent\\app\\services\\telegram_bot.py:412")
    app = ApplicationBuilder().token(TELEGRAM_BOT_API_KEY).build()
    
    # Add handlers
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, do_command))
    app.add_handler(CommandHandler("connect", connect))
    app.add_handler(CommandHandler("rag", rag_command))
    
    app.run_polling()


if __name__ == "__main__":
    run_bot()