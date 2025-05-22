from app.config import db
from datetime import datetime

COLLECTION_NAME = "workflows"

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
