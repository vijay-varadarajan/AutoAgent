"""
Tool registry and factory for creating Google service tools with user credentials.
"""
import logging
from typing import Dict, List, Type, Any
from langchain.tools import BaseTool
from app.tools.base_tool import BaseGoogleTool
from app.logging_config import setup_logging  # Import centralized logging

# Get logger (centralized logging already configured)
logger = logging.getLogger(__name__)

# Import all tool classes
from app.tools.gmail_tools import SendEmailTool, ReadEmailTool
# TODO: Add other tool imports when they are created
# from app.tools.calendar_tools import CreateCalendarEventTool, ViewCalendarEventsTool
# from app.tools.drive_tools import DriveUploadTool, DriveSearchTool
# from app.tools.sheets_tools import CreateSpreadsheetTool, UpdateSpreadsheetTool, ReadSpreadsheetTool
# from app.tools.docs_tools import CreateDocumentTool, UpdateDocumentTool, ReadDocumentTool
# from app.tools.slides_tools import CreatePresentationTool, AddSlideTool, ReadPresentationTool
# from app.tools.photos_tools import PhotoUploadTool, ListPhotosTool
# from app.tools.meet_tools import CreateMeetingTool, ListMeetingsTool

# Action to tool class mapping
TOOL_REGISTRY: Dict[str, Type[BaseGoogleTool]] = {
    # Email actions
    "email": SendEmailTool,
    "read_email": ReadEmailTool,
    
    # TODO: Add other actions when tools are created
    # # Calendar actions
    # "calendar_event": CreateCalendarEventTool,
    # "view_calendar": ViewCalendarEventsTool,
    # 
    # # Drive actions
    # "drive_upload": DriveUploadTool,
    # "search_drive": DriveSearchTool,
    # 
    # # Spreadsheet actions
    # "spreadsheet": CreateSpreadsheetTool,
    # "update_spreadsheet": UpdateSpreadsheetTool,
    # "read_spreadsheet": ReadSpreadsheetTool,
    # 
    # # Document actions
    # "document": CreateDocumentTool,
    # "update_document": UpdateDocumentTool,
    # "read_document": ReadDocumentTool,
    # 
    # # Presentation actions
    # "presentation": CreatePresentationTool,
    # "add_slide": AddSlideTool,
    # "read_presentation": ReadPresentationTool,
    # 
    # # Photo actions
    # "photo_upload": PhotoUploadTool,
    # "list_photos": ListPhotosTool,
    # 
    # # Meet actions
    # "meet": CreateMeetingTool,
    # "list_meetings": ListMeetingsTool,
}

def create_tool_for_action(action: str, user_id: str) -> BaseGoogleTool:
    """
    Create a tool instance for the given action and user.
    
    Args:
        action: The action type (e.g., 'email', 'calendar_event')
        user_id: The user ID for credential retrieval
        
    Returns:
        Configured tool instance
        
    Raises:
        ValueError: If action is not supported
    """
    logger.info(f"🔧 TOOL REGISTRY: Creating tool for action '{action}' and user {user_id}")
    
    if action not in TOOL_REGISTRY:
        supported_actions = list(TOOL_REGISTRY.keys())
        error_msg = f"Unsupported action '{action}'. Supported actions: {supported_actions}"
        logger.error(f"🔧 TOOL REGISTRY: ❌ {error_msg}")
        raise ValueError(error_msg)
    
    tool_class = TOOL_REGISTRY[action]
    logger.info(f"🔧 TOOL REGISTRY: Found tool class: {tool_class.__name__}")
    
    try:
        tool_instance = tool_class(user_id=user_id)
        logger.info(f"🔧 TOOL REGISTRY: ✅ Successfully created {tool_instance.name} for user {user_id}")
        return tool_instance
    except Exception as e:
        logger.error(f"🔧 TOOL REGISTRY: ❌ Failed to create tool {tool_class.__name__}: {e}")
        raise

def create_tools_for_workflow(workflow_tasks: List[Dict], user_id: str) -> List[BaseGoogleTool]:
    """
    Create tool instances for all actions in a workflow.
    
    Args:
        workflow_tasks: List of task dictionaries with 'action' keys
        user_id: The user ID for credential retrieval
        
    Returns:
        List of configured tool instances
    """
    tools = []
    for task in workflow_tasks:
        action = task.get('action')
        if action and action in TOOL_REGISTRY:
            try:
                tool = create_tool_for_action(action, user_id)
                tools.append(tool)
            except Exception as e:
                # Log error but continue with other tools
                print(f"Warning: Failed to create tool for action '{action}': {e}")
    
    return tools

def get_available_actions() -> List[str]:
    """Get list of all available action types."""
    return list(TOOL_REGISTRY.keys())

def get_tool_descriptions() -> Dict[str, str]:
    """Get descriptions for all available tools."""
    descriptions = {}
    for action, tool_class in TOOL_REGISTRY.items():
        # Create a temporary instance to get description
        try:
            temp_tool = tool_class(user_id="temp")
            descriptions[action] = temp_tool.description
        except Exception:
            descriptions[action] = f"Tool for {action} action"
    
    return descriptions
