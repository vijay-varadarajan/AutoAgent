from fastapi import APIRouter, HTTPException
import logging
from app.logging_config import setup_logging  # Import centralized logging
from app.schemas.workflow import WorkflowRequest
from app.schemas.workflow_status import StatusUpdateRequest, LogEntryRequest
from app.services.gemini_parser import parse_workflow
from app.services.firestore_db import (
    save_workflow, 
    get_all_workflows, 
    get_workflow_by_id,
    update_workflow_status,
    add_execution_log_entry,
    get_workflows_by_status,
    get_pending_workflows,
    get_workflow_execution_summary,
    WorkflowStatus,
    LogEntryType
)
from app.services.workflow_utils import get_workflow_health_status, retry_failed_workflow
from app.services.enhanced_workflow_executor import EnhancedWorkflowExecutor
from app.services.enhanced_workflow_executor import execute_workflow_with_tools

# Get logger (centralized logging already configured)
logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/parse-and-save")
async def parse_and_save(req: WorkflowRequest):
    logger.info(f"🚀 WORKFLOW API: Received parse-and-save request from user {req.user_id}")
    logger.info(f"🚀 WORKFLOW API: Prompt: '{req.prompt[:100]}...'")
    
    try:
        # Parse the workflow
        logger.info("🚀 WORKFLOW API: Calling Gemini parser...")
        structured_output = await parse_workflow(req.prompt)
        logger.info(f"🚀 WORKFLOW API: Parser returned type: {type(structured_output)}, {structured_output}")
        
        # Validate that structured_output is a dictionary
        if not isinstance(structured_output, dict):
            error_msg = f"Expected dict from parse_workflow, got {type(structured_output)}: {structured_output}"
            logger.error(f"🚀 WORKFLOW API: ❌ {error_msg}")
            raise ValueError(error_msg)
        
        logger.info("🚀 WORKFLOW API: ✅ Parser returned valid dictionary")
        
        # Ensure tasks exist
        if "tasks" not in structured_output:
            logger.warning("🚀 WORKFLOW API: No 'tasks' key found, adding empty tasks array")
            structured_output["tasks"] = []
        
        task_count = len(structured_output.get("tasks", []))
        logger.info(f"🚀 WORKFLOW API: Found {task_count} tasks in workflow")
        
        # Save workflow with initial status
        logger.info("🚀 WORKFLOW API: Saving workflow to Firebase...")

        # remove the workflows that have action of 'conversation' and mode of 'unsupported'
        workflows_only = structured_output.copy()
        workflows_only["tasks"] = [
            task for task in workflows_only["tasks"] 
            if not (task.get("action") == "conversation" and task.get("mode") == "unsupported")
        ]
        logger.info(f"🚀 WORKFLOW API: Filtered tasks, remaining {len(workflows_only['tasks'])} tasks")
        
        conversations = [task for task in structured_output["tasks"] if task.get('action') == 'conversation']
        print(f"Conversations found: {conversations}")
        if conversations:
            logger.info(f"🚀 WORKFLOW API: Found {len(conversations)} conversation tasks, sending Gemini response...")
            return {"status": "saved", "workflow_id": 'conversation_001', "workflow": conversations}

        if not workflows_only["tasks"]:
            logger.warning("🚀 WORKFLOW API: No valid tasks found after filtering, returning empty workflow")
            workflows_only = {"frequency": "once", "tasks": []}

        for task in workflows_only["tasks"]:
            if task.get("action") == "email" and task.get("mode") == "write":
                if not task.get("subject"):
                    logger.warning("🚀 WORKFLOW API: Email task found without subject, skipping")
                    return None
                elif not task.get("body"):
                    logger.warning("🚀 WORKFLOW API: Email task found without body, skipping")
                    return None
        
        workflow_id = save_workflow(req.user_id, req.prompt, workflows_only)
        logger.info(f"🚀 WORKFLOW API: ✅ Workflow saved with ID: {workflow_id}")
        
        # Log the initial creation
        logger.info("🚀 WORKFLOW API: Adding execution log entry...")
        add_execution_log_entry(
            workflow_id, 
            LogEntryType.INFO, 
            "Workflow created and parsed successfully",
            details={
                "prompt_length": len(req.prompt), 
                "parsed_tasks": len(structured_output.get("tasks", [])),
                "workflow_structure": str(structured_output)[:200]  # First 200 chars for debugging
            }
        )
        logger.info("🚀 WORKFLOW API: ✅ Execution log entry added")
        
        # Return the parsed workflow as well for downstream logic
        response_data = {"status": "saved", "workflow_id": workflow_id, "workflow": workflows_only}
        logger.info(f"🚀 WORKFLOW API: ✅ Returning success response for workflow {workflow_id}")
        logger.debug(f"🚀 WORKFLOW API: Response data: {response_data}")
        return response_data
        
    except Exception as e:
        # Enhanced error handling
        logger.error(f"🚀 WORKFLOW API: ❌ Exception occurred: {type(e).__name__}: {str(e)}")
        
        error_details = {
            "error_type": type(e).__name__,
            "error_message": str(e),
            "prompt": req.prompt,
            "user_id": req.user_id
        }
        
        # If we have a workflow_id, log the error
        if 'workflow_id' in locals():
            logger.info(f"🚀 WORKFLOW API: Adding error log entry for workflow {workflow_id}")
            add_execution_log_entry(
                workflow_id, 
                LogEntryType.ERROR, 
                f"Failed to process workflow: {str(e)}",
                error_code="PARSE_ERROR",
                details=error_details
            )
            update_workflow_status(workflow_id, WorkflowStatus.FAILED)
            logger.info(f"🚀 WORKFLOW API: Updated workflow {workflow_id} status to FAILED")
        
        # Return detailed error for debugging
        logger.error("🚀 WORKFLOW API: Raising HTTPException with error details")
        raise HTTPException(
            status_code=500, 
            detail={
                "error": "Workflow parsing failed",
                "details": error_details
            }
        )

@router.get("/user/{user_id}")
def get_user_workflows(user_id: str):
    try:
        workflows = get_all_workflows(user_id)
        return {"workflows": workflows}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{workflow_id}")
def get_workflow(workflow_id: str):
    """Get a specific workflow by ID."""
    try:
        workflow = get_workflow_by_id(workflow_id)
        if not workflow:
            raise HTTPException(status_code=404, detail="Workflow not found")
        return {"workflow": workflow}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{workflow_id}/status")
def update_status(workflow_id: str, request: StatusUpdateRequest):
    """Update the status of a workflow."""
    try:
        success = update_workflow_status(workflow_id, request.status)
        if not success:
            raise HTTPException(status_code=404, detail="Workflow not found or update failed")
        
        # Log the status change
        add_execution_log_entry(
            workflow_id,
            LogEntryType.INFO,
            f"Status updated to {request.status}",
            details={"new_status": request.status}
        )
        
        return {"status": "updated", "new_status": request.status}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{workflow_id}/log")
def add_log_entry(workflow_id: str, request: LogEntryRequest):
    """Add an entry to the workflow's execution log."""
    try:
        success = add_execution_log_entry(
            workflow_id, 
            request.entry_type, 
            request.message, 
            request.details, 
            request.tool_name, 
            request.error_code
        )
        if not success:
            raise HTTPException(status_code=404, detail="Workflow not found or log entry failed")
        return {"status": "logged"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/user/{user_id}/status/{status}")
def get_workflows_by_status_endpoint(user_id: str, status: WorkflowStatus):
    """Get workflows for a user filtered by status."""
    try:
        workflows = get_workflows_by_status(user_id, status)
        return {"workflows": workflows, "count": len(workflows)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{workflow_id}/summary")
def get_execution_summary(workflow_id: str):
    """Get execution summary for a workflow."""
    try:
        summary = get_workflow_execution_summary(workflow_id)
        if not summary:
            raise HTTPException(status_code=404, detail="Workflow not found")
        return {"summary": summary}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/user/{user_id}/health")
def get_user_workflow_health(user_id: str):
    """Get overall health status of workflows for a user."""
    try:
        health_status = get_workflow_health_status(user_id)
        return {"health": health_status}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{workflow_id}/retry")
def retry_workflow(workflow_id: str):
    """Retry a failed workflow by resetting it to pending status."""
    try:
        success = retry_failed_workflow(workflow_id)
        if not success:
            raise HTTPException(status_code=400, detail="Workflow cannot be retried or not found")
        return {"status": "workflow_reset_for_retry", "workflow_id": workflow_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/user/{user_id}/execute-pending")
async def execute_pending_workflows(user_id: str):
    """Execute all pending workflows for a user after OAuth completion."""
    try:
        pending_workflows = get_pending_workflows(user_id)
        
        if not pending_workflows:
            return {"message": "No pending workflows found", "executed": 0}
        
        executed_count = 0
        results = []
        
        for workflow_data in pending_workflows:
            workflow_id = workflow_data.get('workflow_id')
            if not workflow_id:
                continue
                
            try:
                executor = EnhancedWorkflowExecutor(workflow_id)
                if executor.load_workflow():
                    success = await executor.execute_workflow()
                    results.append({
                        "workflow_id": workflow_id,
                        "success": success
                    })
                    if success:
                        executed_count += 1
                else:
                    results.append({
                        "workflow_id": workflow_id,
                        "success": False,
                        "error": "Failed to load workflow"
                    })
            except Exception as e:
                results.append({
                    "workflow_id": workflow_id,
                    "success": False,
                    "error": str(e)
                })
        
        return {
            "message": f"Executed {executed_count} out of {len(pending_workflows)} pending workflows",
            "executed": executed_count,
            "total": len(pending_workflows),
            "results": results
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{workflow_id}/execute")
def execute_workflow_endpoint(workflow_id: str):
    """Execute a workflow using LangChain tools for Google API integration."""
    try:
        print(f"Executing workflow {workflow_id} with tools...")
        success = execute_workflow_with_tools(workflow_id)
        if not success:
            raise HTTPException(status_code=400, detail="Workflow execution failed")
        return {"status": "workflow_executed", "workflow_id": workflow_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))



# @router.post("/{workflow_id}/execute")
# async def execute_workflow_endpoint(workflow_id: str):
#     """Execute a workflow using the enhanced workflow executor."""
#     try:
#         executor = EnhancedWorkflowExecutor(workflow_id)
        
#         # Load workflow
#         if not executor.load_workflow():
#             raise HTTPException(status_code=404, detail="Workflow not found or could not be loaded")
        
#         # Execute workflow
#         success = await executor.execute_workflow()
        
#         if success:
#             return {
#                 "status": "execution_completed",
#                 "workflow_id": workflow_id,
#                 "final_status": "completed"
#             }
#         else:
#             return {
#                 "status": "execution_failed", 
#                 "workflow_id": workflow_id,
#                 "final_status": "failed"
#             }
        
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))
