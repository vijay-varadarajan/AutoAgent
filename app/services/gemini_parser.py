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

        full_prompt = f"""You are an AI agent named AutoAgent. This is what you can do: You allow people to send emails to anybody / read emails from their Gmail, by just sending you a message to do so. By giving you a /rag command followed by a <website_link> [<web_link2> <web_link3>] you can be prompted to become an educated Agent who knows about that website's content. 
        
        Now, respond to the following message in a concise, friendly and engaging manner, announcing your name and both of your purposes - email actions and RAG ability. (Add few emojis to make it more engaging):
        {prompt}"""
        
        response = model.generate_content(full_prompt)
        
        await update.message.reply_text(f"{response.text}")
        
    except Exception as e:
        logger.error(f"Gemini conversation error: {e}")
        await update.message.reply_text("Sorry, I couldn't process that as a conversation.")
        

async def parse_workflow(prompt: str) -> dict:
    print(f"Executing function parse_workflow from c:\\Users\\vijay\\Documents\\Agentic AI\\AutoAgent\\app\\services\\gemini_parser.py:12")
    
    model = genai.GenerativeModel("gemini-2.0-flash-lite-001")
    
    full_prompt = f"""
    You are a task parser. Convert the following natural language into a structured JSON format.
    
    Only use the following actions for tasks: email. Do not use any other actions. The supported modes are read, send. Do not use any other modes. The only exception is that, if the message of the user does not relate to any of the supported actions or modes, return a task with action as 'conversation' and mode as 'unsupported', with a message indicating that the action or mode is unsupported.

    If the action is email, when filling out the JSON, ensure that you adhere to the best principles of writing the values for each key (such as recipient, subject, body, query etc) as they are used in the context of the action and mode. For example, for email actions send mode, ensure the recipient is a valid email address, subject is concise, body is clear, etc. And for read actions, ensure the query is specific, structured like gmail search query and relevant to the data being read.
    
    IMPORTANT: Add only as many tasks as specified in the prompt. Do not add any extra tasks or fields. Remember you are able to support multiple tasks, so you can return multiple tasks in the JSON. If the prompt does not specify any tasks, return an empty list of tasks.
    
    Prompt: "{prompt}"

    Return ONLY valid JSON in this exact format, no extra text:
    {{
        "frequency": "once",
        "tasks": [  
            {{"action": "email", "mode": "send", "recipient": "user@example.com", "subject": "Subject", "body": "Email content"}},
            {{"action": "email", "mode": "read", "query": "Search query", max_results: 5}},
            {{"action": "email", "mode": "unsupported", "message": "Unsupported <action or mode>: <action> or <mode> requested"}},
        ]
    }}
    """
    
    try:
        response = model.generate_content(full_prompt)
        response_text = response.text.strip()
        
        # Extract JSON from response (remove any markdown formatting)
        json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
        if json_match:
            json_str = json_match.group(0)
        else:
            json_str = response_text
        
        try:
            # Parse the JSON string into a dictionary
            parsed_data = json.loads(json_str)
            return parsed_data
        
        except json.JSONDecodeError as e:
            # If parsing fails, return a fallback structure
            logger.error(f"🧠 GEMINI PARSER: ❌ JSON parsing failed: {e}")
            fallback_data = {
                "frequency": "once",
                "tasks": [
                    {
                        "action": "email",
                        "mode": "send",
                        "recipient": "error@example.com",
                        "subject": "Parsing Error",
                        "body": f"Failed to parse workflow from prompt: {prompt}"
                    }
                ],
                "error": "Failed to parse Gemini response",
                "raw_response": response_text
            }
            return fallback_data
            
    except Exception as e:
        logger.error(f"🧠 GEMINI PARSER: ❌ Gemini API call failed: {e}")
        fallback_data = {
            "frequency": "once",
            "tasks": [],
            "error": f"Gemini API error: {str(e)}",
            "raw_response": ""
        }
        return fallback_data


'''
           {{"action": "calendar_event", "title": "Meeting Title", "start_time": "2025-07-22T14:00:00", "description": "Meeting description"}},
            {{"action": "drive_upload", "file_name": "document.pdf", "folder_name": "Documents"}},
            {{"action": "spreadsheet", "name": "Sheet Name", "data": [["Header1", "Header2"]]}},
            {{"action": "document", "title": "Document Title", "content": "Document content"}},
            {{"action": "presentation", "title": "Presentation Title", "slides": []}},
            {{"action": "photo_upload", "album_name": "Album Name"}},
            {{"action": "meet", "title": "Meeting Title", "start_time": "2025-07-22T14:00:00"}}
'''