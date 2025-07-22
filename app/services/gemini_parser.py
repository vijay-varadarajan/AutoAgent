import google.generativeai as genai
import json
import re
import logging
from app.config import GEMINI_API_KEY
from app.logging_config import setup_logging  # Import centralized logging

# Get logger (centralized logging already configured)
logger = logging.getLogger(__name__)

genai.configure(api_key=GEMINI_API_KEY)

async def parse_workflow(prompt: str) -> dict:
    logger.info(f"🧠 GEMINI PARSER: Starting workflow parsing for prompt: '{prompt[:100]}...'")
    
    model = genai.GenerativeModel("gemini-2.0-flash-lite-001")
    logger.info(f"🧠 GEMINI PARSER: Initialized Gemini model: {model.model_name}")
    
    full_prompt = f"""
    You are a task parser. Convert the following natural language into a structured JSON format.
    
    Only use the following actions for tasks: email, calendar_event, drive_upload, spreadsheet, document, presentation, photo_upload, meet. Do not use any other actions. If the user requests an unsupported action, ignore it and only include supported actions in the output.

    Prompt: "{prompt}"

    Return ONLY valid JSON in this exact format, no extra text:
    {{
        "frequency": "once",
        "tasks": [  
            {{"action": "email", "recipient": "user@example.com", "subject": "Subject", "body": "Email content"}},
            {{"action": "calendar_event", "title": "Meeting Title", "start_time": "2025-07-22T14:00:00", "description": "Meeting description"}},
            {{"action": "drive_upload", "file_name": "document.pdf", "folder_name": "Documents"}},
            {{"action": "spreadsheet", "name": "Sheet Name", "data": [["Header1", "Header2"]]}},
            {{"action": "document", "title": "Document Title", "content": "Document content"}},
            {{"action": "presentation", "title": "Presentation Title", "slides": []}},
            {{"action": "photo_upload", "album_name": "Album Name"}},
            {{"action": "meet", "title": "Meeting Title", "start_time": "2025-07-22T14:00:00"}}
        ]
    }}
    """
    
    logger.info(f"🧠 GEMINI PARSER: Sending request to Gemini with prompt length: {len(full_prompt)}")
    
    try:
        response = model.generate_content(full_prompt)
        response_text = response.text.strip()
        logger.info(f"🧠 GEMINI PARSER: Received response from Gemini, length: {len(response_text)}")
        logger.debug(f"🧠 GEMINI PARSER: Raw Gemini response: {response_text}")
        
        # Extract JSON from response (remove any markdown formatting)
        logger.info("🧠 GEMINI PARSER: Extracting JSON from response...")
        json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
        if json_match:
            json_str = json_match.group(0)
            logger.info(f"🧠 GEMINI PARSER: Found JSON match, extracted length: {len(json_str)}")
        else:
            json_str = response_text
            logger.warning("🧠 GEMINI PARSER: No JSON pattern found, using full response")
        
        try:
            # Parse the JSON string into a dictionary
            logger.info("🧠 GEMINI PARSER: Parsing JSON string to dictionary...")
            parsed_data = json.loads(json_str)
            logger.info(f"🧠 GEMINI PARSER: ✅ Successfully parsed JSON with {len(parsed_data.get('tasks', []))} tasks")
            logger.debug(f"🧠 GEMINI PARSER: Parsed structure: {parsed_data}")
            return parsed_data
        except json.JSONDecodeError as e:
            # If parsing fails, return a fallback structure
            logger.error(f"🧠 GEMINI PARSER: ❌ JSON parsing failed: {e}")
            logger.error(f"🧠 GEMINI PARSER: Raw response causing error: {response_text}")
            fallback_data = {
                "frequency": "once",
                "tasks": [
                    {
                        "action": "email",
                        "recipient": "error@example.com",
                        "subject": "Parsing Error",
                        "body": f"Failed to parse workflow from prompt: {prompt}"
                    }
                ],
                "error": "Failed to parse Gemini response",
                "raw_response": response_text
            }
            logger.info(f"🧠 GEMINI PARSER: Returning fallback structure with {len(fallback_data['tasks'])} tasks")
            return fallback_data
            
    except Exception as e:
        logger.error(f"🧠 GEMINI PARSER: ❌ Gemini API call failed: {e}")
        fallback_data = {
            "frequency": "once",
            "tasks": [],
            "error": f"Gemini API error: {str(e)}",
            "raw_response": ""
        }
        logger.info("🧠 GEMINI PARSER: Returning empty fallback due to API error")
        return fallback_data
