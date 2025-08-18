# RAGAgent - An Auto-training RAG Agent

RAGAgent is a Telegram bot that automatically trains on user-provided websites to provide intelligent responses using the Gemini model. It supports Retrieval-Augmented Generation (RAG) workflows, allowing users to interact with their own content seamlessly.

## 🛠️ Features
- **RAG Mode**: Automatically trains on user-provided websites.
- **Gemini Integration**: Uses Gemini for intelligent responses.
- **Telegram Bot**: Interact with the agent via Telegram.
- **Web Scraping**: Fetches and processes website content.
- **User Management**: Handles user-specific settings and preferences.
- **Error Handling**: Robust error handling for smooth operation.

## 🔗 Bot Link
[BOT](https://t.me/autoagentv0_bot)

## 🚀 Usage
- Start the bot with `/start`.
- Enable RAG mode with `/rag <website_link>`.
- Ask questions to get responses based on the trained content.
- Disable RAG mode with `/rag`.
- Use `/help` for assistance.
- Chat with the bot in normal mode.

## Tech Stack
- **Python**: Main programming language.
- **Telegram Bot API**: For bot interactions.
- **Gemini**: For generating intelligent responses.
- **ChromaDB**: For vector storage and retrieval.
- **Web Scraping**: For fetching website content.
- **LangChain**: For managing RAG workflows.
- **Langgraph**: For visualizing and managing knowledge graphs.
- **Google Cloud Run**: For hosting and deployment.