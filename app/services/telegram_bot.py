import os
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from app.config import TELEGRAM_BOT_API_KEY, GOOGLE_CLIENT_ID
from app.services.firestore_db import get_google_tokens

BACKEND_URL = "http://localhost:8000/api/workflow/parse-and-save"  # Change if deployed

async def do_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    prompt = " ".join(context.args)
    if not prompt:
        await update.message.reply_text("Please provide an action, e.g. /do summarize news")
        return

    payload = {"user_id": user_id, "prompt": prompt}
    try:
        resp = requests.post(BACKEND_URL, json=payload)
        if resp.status_code == 200:
            data = resp.json()
            await update.message.reply_text(f"Workflow saved! ID: {data['workflow_id']}")
        else:
            await update.message.reply_text(f"Error: {resp.text}")
    except Exception as e:
        await update.message.reply_text(f"Failed to connect to backend: {e}")


# Add this to your telegram_bot.py

from urllib.parse import urlencode

REDIRECT_URI = "http://localhost:8000/api/oauth/callback"  # Update to your backend

def get_google_auth_url(user_id):
    params = {
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": "https://www.googleapis.com/auth/calendar",
        "access_type": "offline",
        "state": user_id,  # To identify the user later
        "prompt": "consent"
    }
    return f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}"

async def connect_calendar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    print(f"User {user_id} requested calendar connection")
    tokens = get_google_tokens(user_id)
    print(f"Retrieved tokens for user {user_id}: {tokens}")
    if tokens:
        await update.message.reply_text("Your Google Calendar is already connected!")
        return
    auth_url = get_google_auth_url(user_id)
    keyboard = [
        [InlineKeyboardButton("Connect Google Calendar", url=auth_url)]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "To connect your Google Calendar, please click the button below and authorize access:",
        reply_markup=reply_markup
    )
    

def run_bot():
    app = ApplicationBuilder().token(TELEGRAM_BOT_API_KEY).build()
    app.add_handler(CommandHandler("do", do_command))
    app.add_handler(CommandHandler("connect_calendar", connect_calendar))
    print("Bot running...")
    app.run_polling()