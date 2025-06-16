import google.generativeai as genai
from app.config import GEMINI_API_KEY

genai.configure(api_key=GEMINI_API_KEY)

async def parse_workflow(prompt: str) -> dict:
    model = genai.GenerativeModel("gemini-2.0-flash-lite-001")
    
    full_prompt = f"""
    You are a task parser. Convert the following natural language into a structured JSON format.
    
    Only use the following actions for tasks: email, calendar_event, drive_upload, spreadsheet, document, presentation, photo_upload, meet. Do not use any other actions. If the user requests an unsupported action, ignore it and only include supported actions in the output.

    Prompt: "{prompt}"

    JSON format:
    {{
        "frequency": "daily",
        "time": "9:00 AM",
        "tasks": [  
            {{"action": "email", "recipient": "me"}},
            {{"action": "calendar_event", "title": "Team Meeting"}},
            {{"action": "drive_upload", "file": "report.pdf"}},
            {{"action": "spreadsheet", "name": "Budget"}},
            {{"action": "document", "name": "Notes"}},
            {{"action": "presentation", "name": "Slides"}},
            {{"action": "photo_upload", "album": "Vacation"}},
            {{"action": "meet", "topic": "Project Sync"}}
        ]
    }}
    """

    response = model.generate_content(full_prompt)
    return response.text
