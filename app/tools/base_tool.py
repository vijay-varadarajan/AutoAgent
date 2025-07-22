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
        super().__init__(user_id=user_id, **kwargs)
        logger.info(f"🔧 BASE TOOL: Initializing {self.__class__.__name__} for user {user_id}")
        logger.info(f"🔧 BASE TOOL: Required scopes: {self.required_scopes}")
    
    def get_credentials(self) -> Optional[Credentials]:
        """Retrieve and refresh Google OAuth credentials for the user."""
        logger.info(f"🔧 BASE TOOL: Getting credentials for user {self.user_id}")
        try:
            # Get tokens from Firebase
            token_data = get_google_tokens(self.user_id)
            if not token_data:
                logger.error(f"🔧 BASE TOOL: ❌ No Google tokens found for user {self.user_id}")
                return None
            
            logger.info(f"🔧 BASE TOOL: ✅ Found token data for user {self.user_id}")
            
            # Check if required scopes are granted
            granted_scopes = set(token_data.get('scope', []))
            required_scopes = set(self.required_scopes)
            logger.info(f"🔧 BASE TOOL: Checking scopes - Required: {required_scopes}")
            logger.info(f"🔧 BASE TOOL: Checking scopes - Granted: {granted_scopes}")
            
            if not required_scopes.issubset(granted_scopes):
                missing_scopes = required_scopes - granted_scopes
                logger.error(f"🔧 BASE TOOL: ❌ Missing required scopes for user {self.user_id}: {missing_scopes}")
                return None
            
            logger.info(f"🔧 BASE TOOL: ✅ All required scopes granted for user {self.user_id}")
            
            # Create credentials object
            logger.info(f"🔧 BASE TOOL: Creating credentials object...")
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
                logger.info(f"🔧 BASE TOOL: Credentials expired, refreshing for user {self.user_id}")
                try:
                    credentials.refresh(Request())
                    
                    # Update Firebase with new tokens
                    updated_tokens = token_data.copy()
                    updated_tokens.update({
                        'access_token': credentials.token,
                        'expires_in': 3600,  # Default expiry
                    })
                    save_google_tokens(self.user_id, updated_tokens)
                    logger.info(f"🔧 BASE TOOL: ✅ Refreshed credentials for user {self.user_id}")
                    
                except Exception as e:
                    logger.error(f"🔧 BASE TOOL: ❌ Failed to refresh credentials for user {self.user_id}: {e}")
                    return None
            else:
                logger.info(f"🔧 BASE TOOL: Credentials are valid for user {self.user_id}")
            
            return credentials
            
        except Exception as e:
            logger.error(f"🔧 BASE TOOL: ❌ Error getting credentials for user {self.user_id}: {e}")
            return None
    
    def handle_api_error(self, error: Exception, operation: str) -> str:
        """Standard error handling for API calls."""
        error_msg = f"Error in {operation}: {str(error)}"
        logger.error(f"User {self.user_id} - {error_msg}")
        return error_msg
