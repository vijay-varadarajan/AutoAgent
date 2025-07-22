from datetime import datetime
from typing import Dict, List, Optional, Any
import base64
from enum import Enum
from firebase_admin import firestore

from app.config import db

# Collection names
WORKFLOWS_COLLECTION = "workflows"
GOOGLE_TOKENS_COLLECTION = "google_tokens"

# Workflow status enumeration
class WorkflowStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

# Execution log entry types
class LogEntryType(str, Enum):
    TOOL_CALL = "tool_call"
    ERROR = "error"
    SUCCESS = "success"
    WARNING = "warning"
    INFO = "info"


def save_workflow(user_id: str, raw_prompt: str, parsed_output: Dict[str, Any]) -> str:
    """Save a workflow to Firestore and return the document ID."""
    doc_ref = db.collection(WORKFLOWS_COLLECTION).document()
    doc_ref.set({
        "user_id": user_id,
        "prompt": raw_prompt,
        "parsed": parsed_output,
        "status": WorkflowStatus.PENDING,
        "execution_log": [],
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
        "timestamp": datetime.utcnow()  # Keep for backward compatibility
    })
    return doc_ref.id


def get_all_workflows(user_id: str) -> List[Dict[str, Any]]:
    """Retrieve all workflows for a specific user."""
    workflows = db.collection(WORKFLOWS_COLLECTION).where("user_id", "==", user_id).stream()
    return [doc.to_dict() for doc in workflows]


def get_workflow_by_id(workflow_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve a specific workflow by its ID."""
    doc = db.collection(WORKFLOWS_COLLECTION).document(workflow_id).get()
    return doc.to_dict() if doc.exists else None


def update_workflow_status(workflow_id: str, status: WorkflowStatus) -> bool:
    """Update the status of a workflow."""
    try:
        doc_ref = db.collection(WORKFLOWS_COLLECTION).document(workflow_id)
        doc_ref.update({
            "status": status,
            "updated_at": datetime.utcnow()
        })
        return True
    except Exception as e:
        print(f"Error updating workflow status: {e}")
        return False


def add_execution_log_entry(
    workflow_id: str, 
    entry_type: LogEntryType, 
    message: str, 
    details: Optional[Dict[str, Any]] = None,
    tool_name: Optional[str] = None,
    error_code: Optional[str] = None
) -> bool:
    """Add an entry to the workflow's execution log."""
    try:
        log_entry = {
            "timestamp": datetime.utcnow(),
            "type": entry_type,
            "message": message
        }
        
        if details:
            log_entry["details"] = details
        if tool_name:
            log_entry["tool_name"] = tool_name
        if error_code:
            log_entry["error_code"] = error_code
        
        doc_ref = db.collection(WORKFLOWS_COLLECTION).document(workflow_id)
        doc_ref.update({
            "execution_log": firestore.ArrayUnion([log_entry]),
            "updated_at": datetime.utcnow()
        })
        return True
    except Exception as e:
        print(f"Error adding execution log entry: {e}")
        return False


def get_workflows_by_status(user_id: str, status: WorkflowStatus) -> List[Dict[str, Any]]:
    """Retrieve workflows for a user filtered by status."""
    workflows = db.collection(WORKFLOWS_COLLECTION)\
        .where("user_id", "==", user_id)\
        .where("status", "==", status)\
        .stream()
    return [doc.to_dict() for doc in workflows]


def get_failed_workflows(user_id: str) -> List[Dict[str, Any]]:
    """Retrieve all failed workflows for a user."""
    return get_workflows_by_status(user_id, WorkflowStatus.FAILED)


def get_pending_workflows(user_id: str) -> List[Dict[str, Any]]:
    """Retrieve all pending workflows for a user."""
    workflows = db.collection(WORKFLOWS_COLLECTION)\
        .where("user_id", "==", user_id)\
        .where("status", "==", WorkflowStatus.PENDING)\
        .stream()
    
    # Include document ID as workflow_id
    result = []
    for doc in workflows:
        workflow_data = doc.to_dict()
        workflow_data['workflow_id'] = doc.id  # Add document ID
        result.append(workflow_data)
    
    return result


def get_workflow_execution_summary(workflow_id: str) -> Optional[Dict[str, Any]]:
    """Get a summary of workflow execution including status and log stats."""
    workflow = get_workflow_by_id(workflow_id)
    if not workflow:
        return None
    
    execution_log = workflow.get("execution_log", [])
    
    # Count log entries by type
    log_counts = {}
    for entry in execution_log:
        entry_type = entry.get("type", "unknown")
        log_counts[entry_type] = log_counts.get(entry_type, 0) + 1
    
    return {
        "workflow_id": workflow_id,
        "status": workflow.get("status"),
        "created_at": workflow.get("created_at"),
        "updated_at": workflow.get("updated_at"),
        "total_log_entries": len(execution_log),
        "log_counts_by_type": log_counts,
        "has_errors": any(entry.get("type") == LogEntryType.ERROR for entry in execution_log),
        "last_activity": execution_log[-1].get("timestamp") if execution_log else workflow.get("created_at")
    }


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


def save_photo(user_id: str, photo_bytes: bytes, file_id: str) -> str:
    """Save a photo to Firestore as base64-encoded string. Returns the document ID."""
    doc_ref = db.collection("photos").document()
    doc_ref.set({
        "user_id": user_id,
        "file_id": file_id,
        "photo_data": base64.b64encode(photo_bytes).decode('utf-8'),
        "timestamp": datetime.utcnow()
    })
    return doc_ref.id

def save_user_chat_info(user_id: str, chat_id: int, username: str = None) -> None:
    """Save user's Telegram chat information for background messaging."""
    doc_ref = db.collection("telegram_users").document(user_id)
    doc_ref.set({
        "chat_id": chat_id,
        "username": username,
        "last_active": datetime.utcnow()
    })

def get_user_chat_id(user_id: str) -> Optional[int]:
    """Get user's Telegram chat ID for background messaging."""
    doc = db.collection("telegram_users").document(user_id).get()
    if doc.exists:
        return doc.to_dict().get("chat_id")
    return None