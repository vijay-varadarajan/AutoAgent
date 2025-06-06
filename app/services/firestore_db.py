from app.config import db
from datetime import datetime

COLLECTION_NAME = "workflows"
GOOGLE_TOKENS_COLLECTION = "google_tokens"

def save_workflow(user_id: str, raw_prompt: str, parsed_output: dict):
    doc_ref = db.collection(COLLECTION_NAME).document()
    doc_ref.set({
        "user_id": user_id,
        "prompt": raw_prompt,
        "parsed": parsed_output,
        "timestamp": datetime.utcnow()
    })
    return doc_ref.id

def get_all_workflows(user_id: str):
    workflows = db.collection(COLLECTION_NAME).where("user_id", "==", user_id).stream()
    return [doc.to_dict() for doc in workflows]


def save_google_tokens(user_id: str, tokens: dict):
    """
    Save Google OAuth tokens for a user.
    """
    doc_ref = db.collection(GOOGLE_TOKENS_COLLECTION).document(user_id)
    doc_ref.set(tokens)

def get_google_tokens(user_id: str):
    """
    Retrieve Google OAuth tokens for a user.
    """
    doc = db.collection(GOOGLE_TOKENS_COLLECTION).document(user_id).get()
    if doc.exists:
        return doc.to_dict()
    return None