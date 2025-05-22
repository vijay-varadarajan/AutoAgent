import google.generativeai as genai
from app.config import GEMINI_API_KEY

genai.configure(api_key=GEMINI_API_KEY)

async def parse_workflow(prompt: str) -> dict:
    model = genai.GenerativeModel("gemini-2.0-flash-lite-001")
    
    full_prompt = f"""
    You are a task parser. Convert the following natural language into a structured JSON format.

    Prompt: "{prompt}"

    JSON format:
    {{
        "frequency": "daily",
        "time": "9:00 AM",
        "tasks": [
            {{"action": "summarize", "source": "Hacker News"}},
            {{"action": "generate_insights", "topic": "investments"}},
            {{"action": "email", "recipient": "me"}},
            {{"action": "telegram_alert", "recipient": "me"}}
        ]
    }}
    """

    response = model.generate_content(full_prompt)
    return response.text
