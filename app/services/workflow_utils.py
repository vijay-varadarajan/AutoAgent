"""
Workflow utilities for common operations and helper functions.
"""
from typing import Dict, Any, List, Optional
from datetime import datetime
from app.services.firestore_db import (
    update_workflow_status,
    add_execution_log_entry,
    get_workflow_by_id,
    WorkflowStatus,
    LogEntryType
)

class WorkflowExecutor:
    """Helper class for executing workflows with proper logging and status tracking."""
    
    def __init__(self, workflow_id: str):
        self.workflow_id = workflow_id
        self.workflow_data = None
        
    def load_workflow(self) -> bool:
        """Load workflow data from Firestore."""
        self.workflow_data = get_workflow_by_id(self.workflow_id)
        return self.workflow_data is not None
    
    def start_execution(self) -> bool:
        """Mark workflow as in progress and log start."""
        success = update_workflow_status(self.workflow_id, WorkflowStatus.IN_PROGRESS)
        if success:
            add_execution_log_entry(
                self.workflow_id,
                LogEntryType.INFO,
                "Workflow execution started",
                details={"start_time": datetime.utcnow().isoformat()}
            )
        return success
    
    def complete_execution(self, results: Optional[Dict[str, Any]] = None) -> bool:
        """Mark workflow as completed and log completion."""
        success = update_workflow_status(self.workflow_id, WorkflowStatus.COMPLETED)
        if success:
            add_execution_log_entry(
                self.workflow_id,
                LogEntryType.SUCCESS,
                "Workflow execution completed successfully",
                details={"completion_time": datetime.utcnow().isoformat(), "results": results}
            )
        return success
    
    def fail_execution(self, error_message: str, error_code: Optional[str] = None) -> bool:
        """Mark workflow as failed and log error."""
        success = update_workflow_status(self.workflow_id, WorkflowStatus.FAILED)
        if success:
            add_execution_log_entry(
                self.workflow_id,
                LogEntryType.ERROR,
                f"Workflow execution failed: {error_message}",
                error_code=error_code,
                details={"failure_time": datetime.utcnow().isoformat()}
            )
        return success
    
    def log_tool_execution(self, tool_name: str, success: bool, details: Optional[Dict[str, Any]] = None):
        """Log a tool execution attempt."""
        entry_type = LogEntryType.SUCCESS if success else LogEntryType.ERROR
        message = f"Tool '{tool_name}' executed {'successfully' if success else 'with errors'}"
        
        add_execution_log_entry(
            self.workflow_id,
            entry_type,
            message,
            tool_name=tool_name,
            details=details
        )
    
    def log_info(self, message: str, details: Optional[Dict[str, Any]] = None):
        """Log an informational message."""
        add_execution_log_entry(
            self.workflow_id,
            LogEntryType.INFO,
            message,
            details=details
        )
    
    def log_warning(self, message: str, details: Optional[Dict[str, Any]] = None):
        """Log a warning message."""
        add_execution_log_entry(
            self.workflow_id,
            LogEntryType.WARNING,
            message,
            details=details
        )

def get_workflow_health_status(user_id: str) -> Dict[str, Any]:
    """Get overall health status of workflows for a user."""
    from app.services.firestore_db import get_workflows_by_status
    
    pending_count = len(get_workflows_by_status(user_id, WorkflowStatus.PENDING))
    in_progress_count = len(get_workflows_by_status(user_id, WorkflowStatus.IN_PROGRESS))
    completed_count = len(get_workflows_by_status(user_id, WorkflowStatus.COMPLETED))
    failed_count = len(get_workflows_by_status(user_id, WorkflowStatus.FAILED))
    
    total_workflows = pending_count + in_progress_count + completed_count + failed_count
    
    return {
        "user_id": user_id,
        "total_workflows": total_workflows,
        "pending": pending_count,
        "in_progress": in_progress_count,
        "completed": completed_count,
        "failed": failed_count,
        "success_rate": (completed_count / total_workflows * 100) if total_workflows > 0 else 0,
        "failure_rate": (failed_count / total_workflows * 100) if total_workflows > 0 else 0,
        "timestamp": datetime.utcnow()
    }

def retry_failed_workflow(workflow_id: str) -> bool:
    """Reset a failed workflow back to pending status for retry."""
    workflow = get_workflow_by_id(workflow_id)
    if not workflow or workflow.get("status") != WorkflowStatus.FAILED:
        return False
    
    success = update_workflow_status(workflow_id, WorkflowStatus.PENDING)
    if success:
        add_execution_log_entry(
            workflow_id,
            LogEntryType.INFO,
            "Workflow reset for retry",
            details={"retry_time": datetime.utcnow().isoformat()}
        )
    return success
