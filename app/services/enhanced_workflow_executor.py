"""
Enhanced workflow executor that uses LangChain tools for Google API integration.
Includes thinking process display on Telegram.
"""
from typing import Dict, Any, List, Optional
from datetime import datetime
import json
import logging
import asyncio
from app.logging_config import setup_logging  # Import centralized logging

from app.services.background_telegram import background_messenger
from app.services.firestore_db import (
    update_workflow_status,
    add_execution_log_entry,
    get_workflow_by_id,
    WorkflowStatus,
    LogEntryType
)
from app.tools.tool_registry import create_tools_for_workflow, create_tool_for_action
from app.tools.base_tool import BaseGoogleTool

# Get logger (centralized logging already configured)
logger = logging.getLogger(__name__)

class EnhancedWorkflowExecutor:
    """Enhanced workflow executor with LangChain Google API tools and thinking process."""
    
    def __init__(self, workflow_id: str, telegram_update=None):
        print(f"Executing function __init__ from c:\\Users\\vijay\\Documents\\Agentic AI\\AutoAgent\\app\\services\\enhanced_workflow_executor.py:29")
        self.workflow_id = workflow_id
        self.workflow_data = None
        self.user_id = None
        self.tools = {}
        self.telegram_update = telegram_update
        self.thinking_message_id = None
        
        self.use_background_messaging = telegram_update is None  # Use background if no update available
        
        
    def load_workflow(self) -> bool:
        """Load workflow data from Firestore."""
        print(f"Executing function load_workflow from c:\\Users\\vijay\\Documents\\Agentic AI\\AutoAgent\\app\\services\\enhanced_workflow_executor.py:41")
        try:
            self.workflow_data = get_workflow_by_id(self.workflow_id)
            if not self.workflow_data:
                logger.error(f"🔧 EXECUTOR: ❌ Workflow {self.workflow_id} not found in Firestore")
                return False
            
            self.user_id = self.workflow_data.get('user_id')
            if not self.user_id:
                logger.error(f"🔧 EXECUTOR: ❌ No user_id found in workflow {self.workflow_id}")
                return False
            
            # Initialize tools for this workflow
            parsed_data = self.workflow_data.get('parsed', {})
            if isinstance(parsed_data, str):
                try:
                    parsed_data = json.loads(parsed_data)
                except json.JSONDecodeError:
                    logger.error("🔧 EXECUTOR: ❌ Failed to parse workflow data JSON")
                    return False
            
            tasks = parsed_data.get('tasks', [])
            
            # Create tools for each unique action
            unique_action_modes = set(((task.get('action'), task.get('mode')) for task in tasks if task.get('action')))

            for action, mode in unique_action_modes:
                try:
                    tool = create_tool_for_action(action, self.user_id, mode)
                    if tool:
                        self.tools[action] = tool
                    else:
                        logger.warning(f"🔧 EXECUTOR: ⚠️ No tool available for action: {action}")
                except Exception as e:
                    logger.error(f"🔧 EXECUTOR: ❌ Failed to create tool for {action}: {e}")
            
            return True
            
        except Exception as e:
            logger.error(f"🔧 EXECUTOR: ❌ Error loading workflow: {e}")
            return False
        
        
    def load_workflow(self) -> bool:
        """Load workflow data from Firestore."""
        print(f"Executing function load_workflow from c:\\Users\\vijay\\Documents\\Agentic AI\\AutoAgent\\app\\services\\enhanced_workflow_executor.py:88")
        try:
            self.workflow_data = get_workflow_by_id(self.workflow_id)
            if not self.workflow_data:
                logger.error(f"Workflow {self.workflow_id} not found")
                return False
            
            self.user_id = self.workflow_data.get('user_id')
            if not self.user_id:
                logger.error(f"No user_id found in workflow {self.workflow_id}")
                return False
            
            # Initialize tools for this workflow
            parsed_data = self.workflow_data.get('parsed', {})
            if isinstance(parsed_data, str):
                try:
                    parsed_data = json.loads(parsed_data)
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse workflow data: {e}")
                    return False
            
            tasks = parsed_data.get('tasks', [])
            self._initialize_tools(tasks)
            
            logger.info(f"Loaded workflow {self.workflow_id} for user {self.user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error loading workflow {self.workflow_id}: {e}")
            return False
    
    
    def _initialize_tools(self, tasks: List[Dict[str, Any]]) -> None:
        print(f"Executing function _initialize_tools from c:\\Users\\vijay\\Documents\\Agentic AI\\AutoAgent\\app\\services\\enhanced_workflow_executor.py:120")
        """Initialize LangChain tools for workflow tasks."""
        try:
            workflow_tools = create_tools_for_workflow(tasks, self.user_id)
            
            # Create a mapping of action -> tool for easy access
            for tool in workflow_tools:
                # Map tool name to the tool instance
                self.tools[tool.name] = tool
            
            logger.info(f"Initialized {len(self.tools)} tools for workflow {self.workflow_id}")
            
        except Exception as e:
            logger.error(f"Error initializing tools for workflow {self.workflow_id}: {e}")
    
    
    async def _send_thinking(self, message: str) -> Optional[int]:
        """Send thinking message to Telegram if available."""
        print(f"Executing function _send_thinking from c:\\Users\\vijay\\Documents\\Agentic AI\\AutoAgent\\app\\services\\enhanced_workflow_executor.py:137")
        
        if self.use_background_messaging:
            # Use background messenger when no telegram_update is available
            return await background_messenger.send_thinking_message(self.user_id, message)
        
        elif self.telegram_update:
            try:
                from app.services.telegram_bot import send_thinking_message
                message_id = await send_thinking_message(self.telegram_update, message)
                return message_id
            except Exception as e:
                logger.error(f"🔧 EXECUTOR: ❌ Error sending thinking message: {e}")
        else:
            logger.info("🔧 EXECUTOR: No Telegram update available, skipping thinking message")
        return None
    
    
    async def _update_thinking(self, message_id: Optional[int], new_message: str):
        """Update thinking message on Telegram if available."""
        print(f"Executing function _update_thinking from c:\\Users\\vijay\\Documents\\Agentic AI\\AutoAgent\\app\\services\\enhanced_workflow_executor.py:157")
        logger.info(f"🔧 EXECUTOR: 📝 Updating thinking message {message_id}: {new_message}")
        
        if self.use_background_messaging:
            # Use background messenger
            await background_messenger.update_thinking_message(self.user_id, new_message)
        
        elif self.telegram_update and message_id:
            try:
                from app.services.telegram_bot import edit_thinking_message
                await edit_thinking_message(self.telegram_update, message_id, new_message)
                logger.info(f"🔧 EXECUTOR: ✅ Thinking message {message_id} updated")
            except Exception as e:
                logger.error(f"🔧 EXECUTOR: ❌ Error updating thinking message: {e}")
        else:
            logger.info(f"🔧 EXECUTOR: No Telegram update or message ID, skipping update")
    
    async def _delete_thinking(self, message_id: Optional[int]):
        print(f"Executing function _delete_thinking from c:\\Users\\vijay\\Documents\\Agentic AI\\AutoAgent\\app\\services\\enhanced_workflow_executor.py:176")
        """Delete thinking message on Telegram if available."""
        logger.info(f"🔧 EXECUTOR: 🗑️ Deleting thinking message {message_id}")
        
        if self.use_background_messaging:
            # Use background messenger
            await background_messenger.delete_thinking_message(self.user_id)
        elif self.telegram_update and message_id:
            try:
                from app.services.telegram_bot import delete_thinking_message
                await delete_thinking_message(self.telegram_update, message_id)
                logger.info(f"🔧 EXECUTOR: ✅ Thinking message {message_id} deleted")
            except Exception as e:
                logger.error(f"🔧 EXECUTOR: ❌ Error deleting thinking message: {e}")
        else:
            logger.info("🔧 EXECUTOR: No Telegram update or message ID, skipping deletion")
    
    async def _send_final_result(self, message: str):
        """Send final result message to user."""
        if self.use_background_messaging:
            await background_messenger.send_final_message(self.user_id, message)
        elif self.telegram_update:
            try:
                await self.telegram_update.message.reply_text(message)
            except Exception as e:
                logger.error(f"🔧 EXECUTOR: ❌ Error sending final message: {e}")

    def start_execution(self) -> bool:
        print(f"Executing function start_execution from c:\\Users\\vijay\\Documents\\Agentic AI\\AutoAgent\\app\\services\\enhanced_workflow_executor.py:204")
        """Mark workflow as in progress and log start."""
        try:
            success = update_workflow_status(self.workflow_id, WorkflowStatus.IN_PROGRESS)
            if success:
                add_execution_log_entry(
                    self.workflow_id,
                    LogEntryType.INFO,
                    "Workflow execution started with LangChain tools",
                    details={
                        "start_time": datetime.utcnow().isoformat(),
                        "available_tools": list(self.tools.keys())
                    }
                )
            return success
        except Exception as e:
            logger.error(f"Error starting workflow execution: {e}")
            return False
    
    def _validate_email_tasks(self, tasks: List[Dict[str, Any]]) -> Optional[str]:
        """Validate email tasks have required fields. Returns error message if validation fails."""
        print(f"Executing function _validate_email_tasks from c:\\Users\\vijay\\Documents\\Agentic AI\\AutoAgent\\app\\services\\enhanced_workflow_executor.py:224")
        missing_fields = []
        
        # Define placeholder values that should be treated as missing
        placeholder_patterns = {
            'recipient': ['recipient@example.com', 'email@example.com', 'user@example.com', 'example@email.com'],
            'subject': ['Subject', 'Email subject', 'Email Subject', 'subject', 'SUBJECT'],
            'query': ['query', 'search query', 'Search Query', 'QUERY', 'search']
        }
        
        for i, task in enumerate(tasks):
            if task.get('action') == 'email':
                task_missing = []
                mode = task.get('mode', 'write')  # Default to write mode for backward compatibility
                
                if mode == 'read':
                    # For read mode, only query is required
                    query = str(task.get('query', '')).strip()
                    if not query or query in placeholder_patterns['query']:
                        task_missing.append('query')
                else:
                    # For write mode (send email), recipient and subject are required
                    recipient = str(task.get('recipient', '')).strip()
                    if not recipient or recipient in placeholder_patterns['recipient']:
                        task_missing.append('recipient')
                    
                    subject = str(task.get('subject', '')).strip()
                    if not subject or subject in placeholder_patterns['subject']:
                        task_missing.append('subject')
                
                if task_missing:
                    missing_fields.extend(task_missing)
        
        if missing_fields:
            # Remove duplicates while preserving order
            unique_missing = []
            seen = set()
            for field in missing_fields:
                if field not in seen:
                    unique_missing.append(field)
                    seen.add(field)
            
            if len(unique_missing) == 1:
                return f"You have not provided {unique_missing[0]}. Please repeat with all required fields."
            else:
                return f"You have not provided {', '.join(unique_missing)}. Please repeat with all required fields."
        
        return None


    async def execute_workflow(self) -> bool:
        """Execute the entire workflow using LangChain tools with thinking process."""
        print(f"Executing function execute_workflow from c:\\Users\\vijay\\Documents\\Agentic AI\\AutoAgent\\app\\services\\enhanced_workflow_executor.py:276")
        logger.info(f"🔧 EXECUTOR: 🚀 Starting workflow execution for {self.workflow_id}")
        try:
            # Send initial thinking message
            logger.info("🔧 EXECUTOR: Sending initial thinking message...")
            self.thinking_message_id = await self._send_thinking("🤔 Preparing to execute workflow...")
            
            if not self.workflow_data:
                logger.error("🔧 EXECUTOR: ❌ Workflow data not loaded")
                await self._update_thinking(self.thinking_message_id, "❌ Workflow data not loaded")
                return False
            
            # Parse workflow data first for validation
            logger.info("🔧 EXECUTOR: Parsing workflow data for validation...")
            parsed_data = self.workflow_data.get('parsed', {})
            logger.info(f"🔧 EXECUTOR: Parsed workflow data... {parsed_data}")
            if isinstance(parsed_data, str):
                logger.info("� EXECUTOR: Converting string parsed_data to dict...")
                parsed_data = json.loads(parsed_data)
            
            tasks = parsed_data.get('tasks', [])
            logger.info(f"🔧 EXECUTOR: Found {len(tasks)} tasks to execute")
            
            # Validate email tasks before starting execution
            logger.info("🔧 EXECUTOR: Validating email tasks...")
            await self._update_thinking(self.thinking_message_id, "🔍 Validating email requirements...")
            
            validation_error = self._validate_email_tasks(tasks)
            if validation_error:
                logger.error(f"🔧 EXECUTOR: ❌ Email validation failed: {validation_error}")
                await self._delete_thinking(self.thinking_message_id)
                
                # Send error message to user via Telegram
                if self.telegram_update:
                    await self.telegram_update.message.reply_text(f"❌ {validation_error}")
                
                self.fail_execution(f"Email validation failed: {validation_error}", "VALIDATION_ERROR")
                return False
            
            # Check permissions
            logger.info("🔧 EXECUTOR: Checking permissions...")
            await self._update_thinking(self.thinking_message_id, "🔍 Checking permissions...")
            
            # Start execution
            logger.info("🔧 EXECUTOR: Starting execution...")
            if not self.start_execution():
                logger.error("🔧 EXECUTOR: ❌ Failed to start execution")
                await self._update_thinking(self.thinking_message_id, "❌ Failed to start execution")
                return False
            
            await self._update_thinking(self.thinking_message_id, "🚀 Starting workflow execution...")
            
            if not tasks:
                logger.warning("🔧 EXECUTOR: ⚠️ No tasks found in workflow")
                self.log_warning("No tasks found in workflow")
                await self._update_thinking(self.thinking_message_id, "⚠️ No tasks to execute")
                await self._delete_thinking(self.thinking_message_id)
                return self.complete_execution({"message": "No tasks to execute"})
            
            # Execute each task
            logger.info("🔧 EXECUTOR: Starting task execution loop...")
            execution_results = []
            for i, task in enumerate(tasks):
                action = task.get('action', 'unknown')
                logger.info(f"🔧 EXECUTOR: Executing task {i+1}/{len(tasks)}: {action}")
                await self._update_thinking(self.thinking_message_id, f"⚡ Executing {action}...")
                
                task_result = await self._execute_task(task, i + 1)

                execution_results.append(task_result)
                logger.info(f"🔧 EXECUTOR: Task {i+1} result: {'SUCCESS' if task_result.get('success') else 'FAILED'}")
                
                # If a critical task fails, we might want to stop execution
                if not task_result.get('success', False):
                    logger.warning(f"🔧 EXECUTOR: ⚠️ Task {i + 1} failed: {task_result.get('error')}")
                    await self._update_thinking(self.thinking_message_id, f"❌ Failed: {action}")
                    # Continue with other tasks for now, but log the failure
                    self.log_tool_execution(
                        task.get('action', 'unknown'), 
                        False, 
                        {"error": task_result.get('error'), "task_index": i + 1}
                    )
                else:
                    logger.info(f"🔧 EXECUTOR: ✅ Task {i + 1} completed successfully")
                    await self._update_thinking(self.thinking_message_id, f"✅ Completed {action}")
                    
                    self.log_tool_execution(
                        task.get('action', 'unknown'), 
                        True, 
                        {"result": task_result.get('result'), "task_index": i + 1}
                    )
            
            # Complete execution
            successful_tasks = sum(1 for result in execution_results if result.get('success', False))
            logger.info(f"🔧 EXECUTOR: Execution complete - {successful_tasks}/{len(tasks)} tasks successful")
            
            completion_data = {
                "total_tasks": len(tasks),
                "successful_tasks": successful_tasks,
                "failed_tasks": len(tasks) - successful_tasks,
                "execution_results": execution_results
            }
            
            print(f"🔧 EXECUTOR: Execution results: {completion_data}")
            if successful_tasks == len(tasks):
                logger.info("🔧 EXECUTOR: 🎉 All tasks completed successfully!")
                await self._update_thinking(self.thinking_message_id, "🎉 All tasks completed successfully!")
                await self._delete_thinking(self.thinking_message_id)
                await self._send_final_result("🎉 Workflow completed successfully!")
                await self._send_final_result(completion_data['execution_results'][0].get('result', 'No result'))
                return self.complete_execution(completion_data)
            
            elif successful_tasks > 0:
                # Partial success
                logger.warning(f"🔧 EXECUTOR: ⚠️ Partial success - {len(tasks) - successful_tasks} tasks failed")
                self.log_warning(f"Workflow completed with {len(tasks) - successful_tasks} failed tasks")
                await self._update_thinking(self.thinking_message_id, f"⚠️ Completed with {len(tasks) - successful_tasks} failures")
                await self._delete_thinking(self.thinking_message_id)
                await self._send_final_result(f"⚠️ Workflow completed with {len(tasks) - successful_tasks} failures")
                return self.complete_execution(completion_data)
            else:
                # Complete failure
                logger.error("🔧 EXECUTOR: ❌ All tasks failed")
                await self._update_thinking(self.thinking_message_id, "💥 All tasks failed")
                await self._delete_thinking(self.thinking_message_id)
                await self._send_final_result("❌ Workflow failed - all tasks failed")
                
                return self.fail_execution("All tasks failed", "EXECUTION_FAILURE")
            
        except Exception as e:
            error_msg = f"Workflow execution failed: {str(e)}"
            logger.error(f"🔧 EXECUTOR: ❌ {error_msg}")
            await self._update_thinking(self.thinking_message_id, f"💥 Execution failed: {str(e)}")
            await self._delete_thinking(self.thinking_message_id)
            await self._send_final_result(f"💥 Workflow execution failed: {str(e)}")
            
            return self.fail_execution(error_msg, "EXECUTION_ERROR")
    
    async def _execute_task(self, task: Dict[str, Any], task_number: int) -> Dict[str, Any]:
        """Execute a single task using the appropriate LangChain tool."""
        print(f"Executing function _execute_task from c:\\Users\\vijay\\Documents\\Agentic AI\\AutoAgent\\app\\services\\enhanced_workflow_executor.py:414")
        action = task.get('action')
        mode = task.get('mode')  # Default to write mode if not specified
        print(f"🔧 EXECUTOR: Executing task {task_number} with action '{action}' and mode '{mode}'")

        if not action:
            return {
                "success": False,
                "error": "No action specified in task",
                "task": task
            }
        
        if not mode:
            return {
                "success": False,
                "error": "No mode specified in task",
                "task": task
            }
        
        try:
            # Get the appropriate tool
            print(f"🔧 EXECUTOR: Executing task by getting tool for {task_number} with action '{action}'")
            tool = self._get_tool_for_action(action , mode)
            print(f"🔧 EXECUTOR: Using tool '{tool.name}' for action '{action}' and mode '{mode}'")
            if not tool:
                return {
                    "success": False,
                    "error": f"No tool available for action: {action} and mode: {mode}",
                    "task": task
                }
            
            # Prepare tool arguments from task data
            print(f"🔧 EXECUTOR: Preparing arguments for tool '{tool.name}' with action {action} and task {task}")
            tool_args = self._prepare_tool_arguments(action, task, mode)

            if isinstance(tool_args, str):
                try:
                    tool_args = json.loads(tool_args)
                except json.JSONDecodeError:
                    # If it's not valid JSON, wrap it in a dict
                    tool_args = {"input": tool_args}
                    
                    
            print(f"🔧 EXECUTOR: Prepared arguments for tool '{tool.name}': {tool_args}")
            
            
            # Execute the tool
            self.log_info(f"Executing task {task_number}: {action}", {"args": tool_args})
            
            result = tool.run(tool_args)
            
            return {
                "success": True,
                "result": result,
                "action": action,
                "mode": mode,
                "task": task
            }
            
        except Exception as e:
            error_msg = f"Task execution failed: {str(e)}"
            logger.error(f"Task {task_number} ({action}) failed: {error_msg}")
            return {
                "success": False,
                "error": error_msg,
                "action": action,
                "task": task
            }
    
    def _get_tool_for_action(self, action: str, mode: str) -> Optional[BaseGoogleTool]:
        """Get the appropriate tool for an action."""
        print(f"Executing function _get_tool_for_action from c:\\Users\\vijay\\Documents\\Agentic AI\\AutoAgent\\app\\services\\enhanced_workflow_executor.py:484")
        
        # Create a composite key for tool storage
        tool_key = f"{action}_{mode}"
        
        # Check if we already have this specific tool
        if tool_key in self.tools:
            logger.info(f"🔧 EXECUTOR: Reusing existing tool for {action}_{mode}")
            return self.tools[tool_key]
        
        # Create new tool
        try:
            logger.info(f"🔧 EXECUTOR: Creating tool for action: {action} and mode: {mode}")
            tool = create_tool_for_action(action, self.user_id, mode)
            if tool:
                self.tools[tool_key] = tool  # Use composite key
                return tool
            return None
        except Exception as e:
            logger.error(f"Failed to create tool for action {action}: {e}")
            return None

    def _prepare_tool_arguments(self, action: str, task: Dict[str, Any], mode: str) -> Dict[str, Any]:
        """Prepare arguments for tool execution based on action and task data."""
        print(f"Executing function _prepare_tool_arguments from c:\\Users\\vijay\\Documents\\Agentic AI\\AutoAgent\\app\\services\\enhanced_workflow_executor.py:502")
        # Remove the 'action' key and pass the rest as arguments
        args = {k: v for k, v in task.items() if k != 'action'}
        print(f"🔧 EXECUTOR: Preparing arguments for action '{action}': {args}")
        
        # Ensure required fields exist for email actions - only set defaults for optional fields
        if action == 'email':
            
            if mode == 'read':
                # For read mode, only 'query' is required
                if 'query' not in args or not args['query']:
                    raise ValueError("Missing required field 'query' for email read action")
            
            elif mode == 'send':
                # Only handle missing OR None values for optional fields (body, cc, bcc)
                if 'body' not in args or args['body'] is None:
                    args['body'] = ""  # ✅ Fix None values for optional field
                if 'cc' not in args or args['cc'] is None:
                    args['cc'] = ""  # ✅ Optional field
                if 'bcc' not in args or args['bcc'] is None:
                    args['bcc'] = ""  # ✅ Optional field
                # Note: recipient and subject are now validated earlier and should not be empty

        print(f"🔧 EXECUTOR: Final arguments for action '{action}': {args}")
        return args  # ✅ Return dict, not string
    
    
    def complete_execution(self, results: Optional[Dict[str, Any]] = None) -> bool:
    
        """Mark workflow as completed and log completion."""
        print(f"Executing function complete_execution from c:\\Users\\vijay\\Documents\\Agentic AI\\AutoAgent\\app\\services\\enhanced_workflow_executor.py:531")
        try:
            success = update_workflow_status(self.workflow_id, WorkflowStatus.COMPLETED)
            
            if success:
                add_execution_log_entry(
                    self.workflow_id,
                    LogEntryType.SUCCESS,
                    "Workflow execution completed successfully",
                    details={
                        "completion_time": datetime.utcnow().isoformat(), 
                        "results": results
                    }
                )
            
            # send final result message to user
            if results:
                logger.info(f"🔧 EXECUTOR: Sending final results: {results}")
                final_message = results    
                if isinstance(final_message, dict):
                    final_message = json.dumps(final_message, indent=2)
                self._send_final_result(final_message)
                logger.info(f"🔧 EXECUTOR: Final message: {final_message}")
                
            return success, final_message if results else None
        
        except Exception as e:
            logger.error(f"Error completing workflow execution: {e}")
            return False
    
    def fail_execution(self, error_message: str, error_code: Optional[str] = None) -> bool:
        """Mark workflow as failed and log error."""
        print(f"Executing function fail_execution from c:\\Users\\vijay\\Documents\\Agentic AI\\AutoAgent\\app\\services\\enhanced_workflow_executor.py:554")
        try:
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
        except Exception as e:
            logger.error(f"Error failing workflow execution: {e}")
            return False
    
    def log_tool_execution(self, tool_name: str, success: bool, details: Optional[Dict[str, Any]] = None):
        """Log a tool execution attempt."""
        print(f"Executing function log_tool_execution from c:\\Users\\vijay\\Documents\\Agentic AI\\AutoAgent\\app\\services\\enhanced_workflow_executor.py:570")
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


def execute_workflow_with_tools(workflow_id: str) -> bool:
    """
    Convenience function to execute a workflow with LangChain tools.
    
    Args:
        workflow_id: The ID of the workflow to execute
        
    Returns:
        True if execution was successful, False otherwise
    """
    print(f"Executing function execute_workflow_with_tools from c:\\Users\\vijay\\Documents\\Agentic AI\\AutoAgent\\app\\services\\enhanced_workflow_executor.py:605")
    executor = EnhancedWorkflowExecutor(workflow_id)
    
    if not executor.load_workflow():
        logger.error(f"Failed to load workflow {workflow_id}")
        return False
    
    return executor.execute_workflow()
