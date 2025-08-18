from fastapi import FastAPI, Request, HTTPException
from telegram import Update
from telegram.ext import Application
import os
from app.services.telegram_bot import *
from app.config import TELEGRAM_BOT_API_KEY


app = FastAPI(title="RAGAgent API")

# Initialize Telegram bot application
telegram_app = None

@app.on_event("startup")
async def startup_event():
    """Initialize Telegram bot on startup."""
    global telegram_app
    
    if TELEGRAM_BOT_API_KEY:
        telegram_app = Application.builder().token(TELEGRAM_BOT_API_KEY).build()
        
        # Add handlers
        from telegram.ext import CommandHandler, MessageHandler, filters
        
        telegram_app.add_handler(CommandHandler("start", start_command))
        telegram_app.add_handler(CommandHandler("help", help_command))
        telegram_app.add_handler(CommandHandler("rag", rag_command))
        telegram_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, conversation))
        
        # IMPORTANT: Initialize the application
        await telegram_app.initialize()
        
        print("Telegram bot initialized successfully")
    else:
        print("TELEGRAM_BOT_API_KEY not found - Telegram webhook disabled")

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup Telegram bot on shutdown."""
    global telegram_app
    
    if telegram_app:
        await telegram_app.shutdown()
        print("Telegram bot shutdown complete")

@app.post("/webhook/telegram")
async def telegram_webhook(request: Request):
    """Handle Telegram webhook updates."""
    if not telegram_app:
        raise HTTPException(status_code=500, detail="Telegram bot not initialized")
    
    try:
        # Get the raw JSON data
        json_data = await request.json()
        
        # Create Update object from JSON
        update = Update.de_json(json_data, telegram_app.bot)
        
        # Process the update
        await telegram_app.process_update(update)
        
        return {"status": "ok"}
    except Exception as e:
        print(f"Error processing Telegram webhook: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/")
async def root():
    return {"message": "RAGAgent API is running"}

@app.get("/health")
async def health_check():
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8080))
    print(f"Starting server on port {port}")
    uvicorn.run(app, host="0.0.0.0", port=port)
