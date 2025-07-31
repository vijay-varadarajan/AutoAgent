import google.generativeai as genai
import json
import re
import logging
from app.config import GEMINI_API_KEY
from telegram import Update

# Get logger (centralized logging already configured)
logger = logging.getLogger(__name__)

genai.configure(api_key=GEMINI_API_KEY)


async def send_gemini_response(update: Update, prompt: str) -> None:
    """Send a conversational response using Gemini for non-workflow messages."""
    try:
        model = genai.GenerativeModel("gemini-2.0-flash-lite-001")

        full_prompt = f"""You are an AI agent named AutoAgent. This is what you can do: By giving you a /rag command followed by a <website_link> [<web_link2> <web_link3>] you can be prompted to become an educated Agent who knows about that website's content. 
        
        Now, respond to the following message in a concise, friendly and engaging manner. If it is a greeting message, announce your name and your purpose - RAG ability. If it is not, provide your own response to the given prompt (Add few emojis to make it more engaging).

        The prompt is:
        {prompt}"""
        
        response = model.generate_content(full_prompt)
        
        await update.message.reply_text(f"{response.text}")
        
    except Exception as e:
        logger.error(f"Gemini conversation error: {e}")
        await update.message.reply_text("Sorry, I couldn't process that as a conversation.")