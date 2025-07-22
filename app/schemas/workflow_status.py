from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime
from app.services.firestore_db import WorkflowStatus, LogEntryType

class StatusUpdateRequest(BaseModel):
    status: WorkflowStatus

class LogEntryRequest(BaseModel):
    entry_type: LogEntryType
    message: str
    details: Optional[Dict[str, Any]] = None
    tool_name: Optional[str] = None
    error_code: Optional[str] = None

class WorkflowSummary(BaseModel):
    workflow_id: str
    status: Optional[str]
    created_at: Optional[datetime]
    updated_at: Optional[datetime]
    total_log_entries: int
    log_counts_by_type: Dict[str, int]
    has_errors: bool
    last_activity: Optional[datetime]

class WorkflowListResponse(BaseModel):
    workflows: list
    count: int
