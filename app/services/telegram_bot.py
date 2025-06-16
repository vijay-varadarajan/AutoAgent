import json
import logging
from typing import List, Optional, Set, Dict, Any
from urllib.parse import urlencode

import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters

from app.config import TELEGRAM_BOT_API_KEY, GOOGLE_CLIENT_ID
from app.services.firestore_db import get_google_tokens, save_photo

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Constants
BACKEND_URL = "http://localhost:8000/api/workflow/parse-and-save"
REDIRECT_URI = "http://localhost:8000/api/oauth/callback"

# Google OAuth scope mappings
GOOGLE_ACTION_SCOPES = {
    "calendar": "https://www.googleapis.com/auth/calendar",
    "email": "https://mail.google.com/",
    "drive": "https://www.googleapis.com/auth/drive",
    "photos": "https://www.googleapis.com/auth/photoslibrary",
    "meet": "https://www.googleapis.com/auth/meetings.space.created",
    "sheets": "https://www.googleapis.com/auth/spreadsheets",
    "docs": "https://www.googleapis.com/auth/documents",
    "slides": "https://www.googleapis.com/auth/presentations",
}

# Action to scope mapping for workflow tasks
ACTION_SCOPE_MAP = {
    "email": "email",
    "calendar_event": "calendar",
    "drive_upload": "drive",
    "spreadsheet": "sheets",
    "document": "docs",
    "presentation": "slides",
    "photo_upload": "photos",
    "meet": "meet",
}


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


async def handle_backend_response(update: Update, user_id: str, response: requests.Response) -> None:
    """Handle the backend API response."""
    try:
        data = response.json()
    except json.JSONDecodeError:
        data = response.text
    
    if not isinstance(data, dict):
        await update.message.reply_text(f"Unexpected backend response: {data}")
        return
    
    workflow_id = data.get('workflow_id', 'unknown')
    await update.message.reply_text(f"Workflow saved! ID: {workflow_id}")
    
    workflow = data.get("workflow")
    if not workflow:
        return
    
    logger.info(f"Received workflow data from backend for user {user_id}")
    
    required_scopes = extract_required_scopes_from_workflow(workflow)
    logger.info(f"Required scopes: {required_scopes}")
    
    if not required_scopes:
        return
    
    missing_scopes = get_missing_scopes(user_id, required_scopes)
    
    if missing_scopes:
        await send_auth_prompt(update, user_id, list(missing_scopes))
    else:
        await update.message.reply_text("All required Google service permissions are already granted!")


async def do_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle user commands and process workflows. Also handle photo uploads."""
    user_id = str(update.effective_user.id)
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
        await update.message.reply_text("Please provide an action, e.g. 'summarize news'")
        return
    
    payload = {"user_id": user_id, "prompt": prompt}
    
    try:
        response = requests.post(BACKEND_URL, json=payload, timeout=30)
        
        if response.status_code == 200:
            await handle_backend_response(update, user_id, response)
        else:
            await update.message.reply_text(f"Error: {response.text}")
            
    except requests.RequestException as e:
        logger.error(f"Backend request failed for user {user_id}: {e}")
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