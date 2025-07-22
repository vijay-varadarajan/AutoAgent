import json
import logging
import asyncio
from typing import List, Optional, Set, Dict, Any
from urllib.parse import urlencode

import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters

from app.config import TELEGRAM_BOT_API_KEY, GOOGLE_CLIENT_ID
from app.services.firestore_db import get_google_tokens, save_photo, save_user_chat_info
from app.services.enhanced_workflow_executor import EnhancedWorkflowExecutor
from app.logging_config import setup_logging  # Import centralized logging

# Get logger (centralized logging already configured)
logger = logging.getLogger(__name__)

# Constants
BACKEND_URL = "http://localhost:8000/api/workflow/parse-and-save"
REDIRECT_URI = "http://localhost:8000/api/oauth/callback"

# Store for thinking messages (in production, use Redis or database)
thinking_messages = {}

# Google OAuth scope mappings
GOOGLE_ACTION_SCOPES = {
    "email": "https://www.googleapis.com/auth/gmail.send",
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
    logger.info(f"📱 TELEGRAM BOT: Sending thinking message: {message}")
    try:
        sent_message = await update.message.reply_text(
            f"_{message}_",
            parse_mode='Markdown'
        )
        logger.info(f"📱 TELEGRAM BOT: ✅ Thinking message sent with ID: {sent_message.message_id}")
        return sent_message.message_id
    except Exception as e:
        logger.error(f"📱 TELEGRAM BOT: ❌ Error sending thinking message: {e}")
        return None


async def edit_thinking_message(update: Update, message_id: int, new_message: str):
    """Edit an existing thinking message."""
    logger.info(f"📱 TELEGRAM BOT: Editing thinking message {message_id}: {new_message}")
    try:
        await update.get_bot().edit_message_text(
            chat_id=update.effective_chat.id,
            message_id=message_id,
            text=f"_{new_message}_",
            parse_mode='Markdown'
        )
        logger.info(f"📱 TELEGRAM BOT: ✅ Thinking message {message_id} edited successfully")
    except Exception as e:
        logger.error(f"📱 TELEGRAM BOT: ❌ Error editing thinking message: {e}")


async def delete_thinking_message(update: Update, message_id: int):
    """Delete a thinking message."""
    logger.info(f"📱 TELEGRAM BOT: Deleting thinking message {message_id}")
    try:
        await update.get_bot().delete_message(
            chat_id=update.effective_chat.id,
            message_id=message_id
        )
        logger.info(f"📱 TELEGRAM BOT: ✅ Thinking message {message_id} deleted successfully")
    except Exception as e:
        logger.error(f"📱 TELEGRAM BOT: ❌ Error deleting thinking message: {e}")


def get_google_auth_url(user_id: str, scopes: Optional[List[str]] = None) -> str:
    """Generate Google OAuth authorization URL."""
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


def extract_required_scopes_from_workflow(workflow: Any) -> List[str]:
    """Extract required Google OAuth scopes from workflow tasks."""
    parsed_workflow = parse_workflow_json(workflow)
    if not parsed_workflow:
        return []
    
    scopes = set()
    tasks = parsed_workflow.get("tasks", [])
    
    for task in tasks:
        action = task.get("action", "")
        scope_key = ACTION_SCOPE_MAP.get(action)
        if scope_key and scope_key in GOOGLE_ACTION_SCOPES:
            scopes.add(GOOGLE_ACTION_SCOPES[scope_key])
    
    return list(scopes)


def get_missing_scopes(user_id: str, required_scopes: List[str]) -> Set[str]:
    """Determine which scopes are missing for a user."""
    tokens = get_google_tokens(user_id)
    logger.info(f"Retrieved tokens for user {user_id}: {bool(tokens)}")
    
    if not tokens or 'scope' not in tokens:
        return set(required_scopes)
    
    granted_scopes = set(tokens['scope'])
    missing_scopes = set(required_scopes) - granted_scopes
    logger.info(f"Granted scopes: {len(granted_scopes)}, Missing scopes: {len(missing_scopes)}")
    
    return missing_scopes


async def send_auth_prompt(update: Update, user_id: str, missing_scopes: List[str]) -> None:
    """Send authorization prompt with inline keyboard."""
    auth_url = get_google_auth_url(user_id, missing_scopes)
    keyboard = [[InlineKeyboardButton("Connect Google services for this workflow", url=auth_url)]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "To enable this workflow, please connect the required Google services:",
        reply_markup=reply_markup
    )


async def execute_workflow_with_thinking(update: Update, workflow_id: str):
    """Execute workflow and show thinking process."""
    thinking_id = None
    
    try:
        # Send initial thinking message
        thinking_id = await send_thinking_message(update, "🤔 Preparing to execute workflow...")
        
        # Store thinking message ID
        user_id = str(update.effective_user.id)
        thinking_messages[user_id] = thinking_id
        
        # Execute workflow
        executor = EnhancedWorkflowExecutor(workflow_id, update)
        
        # Load workflow
        if not executor.load_workflow():
            await update.message.reply_text("❌ Failed to load workflow")
            return
        
        # Execute workflow with thinking process
        logger.info(f"🔧 EXECUTOR: Starting workflow execution with thinking process...")
        success = await executor.execute_workflow()
        logger.info(f"🔧 EXECUTOR: Workflow execution {'succeeded' if success else 'failed'}")

        # Create result dict for compatibility
        if success:
            result = {"status": "completed"}
        else:
            result = {"status": "failed", "error": "Workflow execution failed"}
        
        # Clean up thinking message
        if thinking_id:
            await delete_thinking_message(update, thinking_id)
        
        # Send final result
        if result.get("status") == "completed":
            await update.message.reply_text("🎉 Workflow completed successfully!")
            
            # Send results summary
            results = result.get("results", {})
            if results:
                summary = "\n".join([f"• {task}: {result}" for task, result in results.items()])
                await update.message.reply_text(f"📊 Results:\n{summary}")
        elif result.get("status") == "failed":
            error_msg = result.get("error", "Unknown error")
            await update.message.reply_text(f"❌ Workflow failed: {error_msg}")
        else:
            await update.message.reply_text(f"⚠️ Workflow status: {result.get('status', 'Unknown')}")
            
    except Exception as e:
        logger.error(f"Error executing workflow: {e}")
        if thinking_id:
            await delete_thinking_message(update, thinking_id)
        await update.message.reply_text(f"💥 Error executing workflow: {str(e)}")
    finally:
        # Clean up thinking messages store
        user_id = str(update.effective_user.id)
        thinking_messages.pop(user_id, None)


def validate_email_workflow(workflow: Any) -> Optional[str]:
    """Validate email workflow has required fields. Returns error message if validation fails."""
    parsed_workflow = parse_workflow_json(workflow)
    if not parsed_workflow:
        return None
    
    missing_fields = []
    tasks = parsed_workflow.get("tasks", [])
    
    # Define placeholder values that should be treated as missing
    placeholder_patterns = {
        'recipient': ['recipient@example.com', 'email@example.com', 'user@example.com', 'example@email.com'],
        'subject': ['Subject', 'Email subject', 'Email Subject', 'subject', 'SUBJECT']
    }
    
    for i, task in enumerate(tasks):
        if task.get('action') == 'email':
            task_missing = []
            
            # Check for recipient
            recipient = str(task.get('recipient', '')).strip()
            if not recipient or recipient in placeholder_patterns['recipient']:
                task_missing.append('recipient')
            
            # Check for subject  
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
            return f"You have not provided {unique_missing[0]}. Please repeat with all required fields."
        else:
            return f"You have not provided {', '.join(unique_missing)}. Please repeat with all required fields."
    
    return None


# Store for pending workflows per user (in production, use Redis or database)
pending_workflows_by_user = {}

async def handle_backend_response(update: Update, user_id: str, response: requests.Response) -> None:
    """Handle the backend API response and start workflow execution."""
    try:
        data = response.json()
    except json.JSONDecodeError:
        data = response.text
    
    if not isinstance(data, dict):
        await update.message.reply_text(f"Unexpected backend response: {data}")
        return
    
    workflow_id = data.get('workflow_id', 'unknown')
    
    # Send initial confirmation
    await update.message.reply_text(f"🎯 Workflow created! ID: {workflow_id}")
    
    workflow = data.get("workflow")
    if not workflow:
        return
    
    logger.info(f"Received workflow data from backend for user {user_id}")
    
    # Validate email workflow requirements before proceeding
    validation_error = validate_email_workflow(workflow)
    if validation_error:
        logger.error(f"📱 TELEGRAM BOT: Email validation failed: {validation_error}")
        await update.message.reply_text(f"❌ {validation_error}")
        return
    
    required_scopes = extract_required_scopes_from_workflow(workflow)
    logger.info(f"Required scopes: {required_scopes}")
    
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
    user_id = str(update.effective_user.id)
    chat_id = update.effective_chat.id
    username = update.effective_user.username

    save_user_chat_info(user_id, chat_id, username)

    prompt = update.message.text.strip() if update.message and update.message.text else ""
    
    logger.info(f"📱 TELEGRAM BOT: Received command from user {user_id}")
    logger.info(f"📱 TELEGRAM BOT: Prompt: '{prompt[:100]}...'")

    # Handle photo upload if present
    if update.message and update.message.photo:
        logger.info(f"📱 TELEGRAM BOT: Photo upload detected from user {user_id}")
        # Get the highest resolution photo
        photo = update.message.photo[-1]
        file_id = photo.file_id
        new_file = await context.bot.get_file(file_id)
        photo_bytes = await new_file.download_as_bytearray()
        # Save photo to Firestore
        save_photo(user_id, photo_bytes, file_id)
        logger.info(f"📱 TELEGRAM BOT: ✅ Photo saved for user {user_id}")
        await update.message.reply_text("Photo uploaded and saved to Firestore!")
        # Optionally, continue to process the prompt if present
        if not prompt:
            logger.info("📱 TELEGRAM BOT: No text prompt with photo, ending processing")
            return

    if not prompt:
        logger.warning(f"📱 TELEGRAM BOT: Empty prompt from user {user_id}")
        await update.message.reply_text("Please provide an action, e.g. 'summarize news'")
        return
    
    payload = {"user_id": user_id, "prompt": prompt}
    logger.info(f"📱 TELEGRAM BOT: Sending request to backend: {BACKEND_URL}")
    logger.debug(f"📱 TELEGRAM BOT: Payload: {payload}")
    
    try:
        logger.info("📱 TELEGRAM BOT: Making HTTP request to backend...")
        response = requests.post(BACKEND_URL, json=payload, timeout=30)
        logger.info(f"📱 TELEGRAM BOT: Backend response status: {response.status_code}")
        
        if response.status_code == 200:
            logger.info("📱 TELEGRAM BOT: ✅ Backend request successful, handling response...")
            await handle_backend_response(update, user_id, response)
        else:
            logger.error(f"📱 TELEGRAM BOT: ❌ Backend error {response.status_code}: {response.text}")
            await update.message.reply_text(f"Error: {response.text}")
            
    except requests.RequestException as e:
        logger.error(f"📱 TELEGRAM BOT: ❌ Backend request failed for user {user_id}: {e}")
        await update.message.reply_text(f"Failed to connect to backend: {e}")


async def connect(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /connect command for Google services authorization."""
    user_id = str(update.effective_user.id)
    logger.info(f"User {user_id} requested Google services connection")
    
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


def run_bot() -> None:
    """Initialize and run the Telegram bot."""
    app = ApplicationBuilder().token(TELEGRAM_BOT_API_KEY).build()
    
    # Add handlers
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, do_command))
    app.add_handler(CommandHandler("connect", connect))
    
    logger.info("Bot starting...")
    app.run_polling()


if __name__ == "__main__":
    run_bot()