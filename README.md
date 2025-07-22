# AutoAgent - LangChain Google API Tools Integration

## 🚀 Quick Start

### Prerequisites Check
```bash
python verify_setup.py
```

### Launch AutoAgent
**Terminal 1 - FastAPI Backend:**
```bash
uvicorn app.main:app --reload
```

**Terminal 2 - Telegram Bot:**
```bash
python run_telegram_bot.py
```

### Test the Integration
Send any of these messages to your Telegram bot:
- `Send an email to test@example.com with subject "Hello from AutoAgent"`
- `Create a calendar event for tomorrow at 2pm titled "Team Meeting"`
- `Upload a file to Google Drive in Documents folder`
- `Create a Google Doc with title "My Report"`

You'll see real-time thinking process:
```
🤔 Preparing to execute workflow...
🔍 Checking permissions...
🚀 Starting workflow execution...
⚡ Executing email...
✅ Completed email
🎉 All tasks completed successfully!
```

## 🛠️ Features

### LangChain Google API Tools (20 tools available)
- **Gmail**: Send/read emails
- **Calendar**: Create/view events 
- **Drive**: Upload/search files
- **Sheets**: Create/update/read spreadsheets
- **Docs**: Create/update/read documents
- **Slides**: Create/add slides/read presentations
- **Photos**: Upload/list photos
- **Meet**: Create/list meetings

### Enhanced Workflow Execution
- ✅ Async processing with real-time updates
- ✅ Thinking process display on Telegram
- ✅ Firebase workflow tracking and persistence
- ✅ OAuth flow integration for Google APIs
- ✅ Comprehensive error handling and retry mechanisms

## 🧪 Testing

```bash
# Basic functionality tests
python test_tools.py

# Telegram integration tests  
python test_telegram_integration.py

# Quick start menu
./start.sh
```

## 📋 Workflow Classification

The system automatically classifies prompts into:
- **Simple question / conversation**: Direct responses
- **Task workflow**: Automated Google API execution with thinking process

## 🔧 Configuration

All configuration is handled through environment variables and JSON files:
- `.env` - API keys and tokens
- `serviceAccountKey.json` - Firebase credentials  
- `google_oauth_client_secret_*.json` - Google OAuth credentials

## 📚 Documentation

- `docs/langchain_tools_integration_complete.md` - Complete technical documentation
- `docs/firebase_enhancement_usage.md` - Firebase integration details
