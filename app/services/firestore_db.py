from datetime import datetime
from typing import Dict, List, Optional, Any

from app.config import db

# Collection names
WORKFLOWS_COLLECTION = "workflows"
GOOGLE_TOKENS_COLLECTION = "google_tokens"


def save_workflow(user_id: str, raw_prompt: str, parsed_output: Dict[str, Any]) -> str:
    """Save a workflow to Firestore and return the document ID."""
    doc_ref = db.collection(WORKFLOWS_COLLECTION).document()
    doc_ref.set({
        "user_id": user_id,
        "prompt": raw_prompt,
        "parsed": parsed_output,
        "timestamp": datetime.utcnow()
    })
    return doc_ref.id


def get_all_workflows(user_id: str) -> List[Dict[str, Any]]:
    """Retrieve all workflows for a specific user."""
    workflows = db.collection(WORKFLOWS_COLLECTION).where("user_id", "==", user_id).stream()
    return [doc.to_dict() for doc in workflows]


def _normalize_scopes(scopes: Any) -> List[str]:
    """Convert scopes to a normalized list format."""
    if isinstance(scopes, str):
        return scopes.split()
    elif isinstance(scopes, list):
        return scopes
    return []


def save_google_tokens(user_id: str, tokens: Dict[str, Any]) -> None:
    """Save Google OAuth tokens for a user, merging scopes with existing ones."""
    doc_ref = db.collection(GOOGLE_TOKENS_COLLECTION).document(user_id)
    
    # Get existing scopes
    existing_scopes = []
    existing_doc = doc_ref.get()
    if existing_doc.exists:
        existing_data = existing_doc.to_dict()
        existing_scopes = _normalize_scopes(existing_data.get("scope", []))
    
    # Merge and deduplicate scopes
    new_scopes = _normalize_scopes(tokens.get("scope", []))
    tokens["scope"] = list(set(existing_scopes + new_scopes))
    
    doc_ref.set(tokens)


def get_google_tokens(user_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve Google OAuth tokens for a user."""
    doc = db.collection(GOOGLE_TOKENS_COLLECTION).document(user_id).get()
    return doc.to_dict() if doc.exists else None