"""
Base tool class and utilities for Google API integration with AutoAgent.
"""
from typing import Optional, Dict, Any, ClassVar, List
from langchain.tools import BaseTool
from pydantic import Field
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from app.services.firestore_db import get_google_tokens, save_google_tokens
from app.config import GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET
import logging
from app.logging_config import setup_logging  # Import centralized logging

# Get logger (centralized logging already configured)
logger = logging.getLogger(__name__)

class BaseGoogleTool(BaseTool):
    """Base class for all Google API tools with OAuth credential management."""
    
    user_id: str = Field(...)
    required_scopes: ClassVar[List[str]] = []
    
    def __init__(self, user_id: str, **kwargs):
        print(f"Executing function __init__ from c:\\Users\\vijay\\Documents\\Agentic AI\\AutoAgent\\app\\tools\\base_tool.py:23")
        super().__init__(user_id=user_id, **kwargs)
    
    def get_credentials(self) -> Optional[Credentials]:
        """Retrieve and refresh Google OAuth credentials for the user."""
        print(f"Executing function get_credentials from c:\\Users\\vijay\\Documents\\Agentic AI\\AutoAgent\\app\\tools\\base_tool.py:28")
        try:
            # Get tokens from Firebase
            token_data = get_google_tokens(self.user_id)
            if not token_data:
                logger.error(f"No Google tokens found for user {self.user_id}")
                return None
            
            # Check if required scopes are granted
            granted_scopes = set(token_data.get('scope', []))
            required_scopes = set(self.required_scopes)
            
            if not required_scopes.issubset(granted_scopes):
                missing_scopes = required_scopes - granted_scopes
                logger.error(f"Missing required scopes for user {self.user_id}: {missing_scopes}")
                return None
            
            # Create credentials object
            credentials = Credentials(
                token=token_data.get('access_token'),
                refresh_token=token_data.get('refresh_token'),
                token_uri="https://oauth2.googleapis.com/token",
                client_id=GOOGLE_CLIENT_ID,
                client_secret=GOOGLE_CLIENT_SECRET,
                scopes=token_data.get('scope', [])
            )
            
            # Refresh if expired
            if credentials.expired and credentials.refresh_token:
                try:
                    credentials.refresh(Request())
                    
                    # Update Firebase with new tokens
                    updated_tokens = token_data.copy()
                    updated_tokens.update({
                        'access_token': credentials.token,
                        'expires_in': 3600,  # Default expiry
                    })
                    save_google_tokens(self.user_id, updated_tokens)
                    
                except Exception as e:
                    logger.error(f"Failed to refresh credentials for user {self.user_id}: {e}")
                    return None
            
            return credentials
            
        except Exception as e:
            logger.error(f"Error getting credentials for user {self.user_id}: {e}")
            return None
    
    def handle_api_error(self, error: Exception, operation: str) -> str:
        """Standard error handling for API calls."""
        print(f"Executing function handle_api_error from c:\\Users\\vijay\\Documents\\Agentic AI\\AutoAgent\\app\\tools\\base_tool.py:91")
        
        error_msg = str(error)
        
        # Check for scope-related errors
        if "invalid_scope" in error_msg or "insufficient permission" in error_msg:
            logger.error(f"User {self.user_id} - Scope error in {operation}: {error_msg}")
            return f"❌ Permission error: You need to re-authorize Google access for {operation}. Please use /connect command."
        
        # Check for authentication errors  
        elif "invalid_grant" in error_msg or "401" in error_msg:
            logger.error(f"User {self.user_id} - Auth error in {operation}: {error_msg}")
            return f"❌ Authentication expired: Please use /connect command to re-authorize Google access."
        
        # General error
        else:
            logger.error(f"User {self.user_id} - Error in {operation}: {error_msg}")
            return f"❌ Error in {operation}: {error_msg}"
