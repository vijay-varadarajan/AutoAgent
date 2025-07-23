"""
Gmail tools for sending emails via Google Gmail API.
"""
from langchain.tools import BaseTool
from pydantic import BaseModel, Field
from typing import ClassVar, List
from googleapiclient.discovery import build
import base64
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from app.tools.base_tool import BaseGoogleTool
import logging

logger = logging.getLogger(__name__)

class SendEmailInput(BaseModel):
    recipient: str = Field(description="The email address of the recipient (required)")
    subject: str = Field(default="", description="The subject of the email (required)")
    body: str = Field(default="", description="The body content of the email") 
    cc: str = Field(default="", description="CC recipients (comma-separated)")
    bcc: str = Field(default="", description="BCC recipients (comma-separated)")
    
    class Config:
        # Allow None values to be converted to defaults
        validate_assignment = True
        
    def __init__(self, **data):
        # Convert None values to empty strings before validation
        for field_name in ['subject', 'body', 'cc', 'bcc']:
            if data.get(field_name) is None:
                data[field_name] = f"<No {field_name.capitalize()}>"
        super().__init__(**data)
        

class SendEmailTool(BaseGoogleTool):
    """Tool for sending emails via Gmail API."""
    
    name: str = "send_email"
    description: str = """Useful for sending emails via Gmail. 
    Requires recipient email address, subject, and body content.
    Optionally supports CC and BCC recipients."""
    args_schema: type[BaseModel] = SendEmailInput
    required_scopes: ClassVar[List[str]] = ['https://www.googleapis.com/auth/gmail.send']
    
    def _run(self, recipient: str, subject: str, body: str, cc: str = "", bcc: str = "") -> str:
        """Send an email using Gmail API."""
        print(f"Executing function _run from c:\\Users\\vijay\\Documents\\Agentic AI\\AutoAgent\\app\\tools\\gmail_tools.py:45")
        try:
            # Get authenticated credentials
            credentials = self.get_credentials()
            if not credentials:
                return "Failed to authenticate with Google Gmail. Please reconnect your Google account."
            
            # Build Gmail service
            service = build('gmail', 'v1', credentials=credentials)
            
            # Create message
            message = MIMEMultipart()
            message['to'] = recipient
            message['subject'] = subject
            
            if cc:
                message['cc'] = cc
            if bcc:
                message['bcc'] = bcc
            
            # Add body
            message.attach(MIMEText(body, 'plain'))
            
            # Encode message
            raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
            
            # Send email
            sent_message = service.users().messages().send(
                userId='me', 
                body={'raw': raw_message}
            ).execute()
            
            result = f"Email sent successfully to {recipient} with message ID: {sent_message['id']}"
            return result
            
        except Exception as e:
            return self.handle_api_error(e, "sending email")
    
    async def _arun(self, recipient: str, subject: str, body: str, cc: str = "", bcc: str = "") -> str:
        """Async version - currently just calls sync version."""
        print(f"Executing function _arun from c:\\Users\\vijay\\Documents\\Agentic AI\\AutoAgent\\app\\tools\\gmail_tools.py:85")
        return self._run(recipient, subject, body, cc, bcc)


class ReadEmailInput(BaseModel):
    query: str = Field(default="", description="Search query for emails (e.g., 'from:someone@example.com')")
    max_results: int = Field(default=10, description="Maximum number of emails to retrieve")

class ReadEmailTool(BaseGoogleTool):
    """Tool for reading/searching emails via Gmail API."""
    
    name: str = "read_email"
    description: str = """Useful for reading and searching emails in Gmail.
    Can filter emails by sender, subject, date, etc. using Gmail search syntax."""
    args_schema: type[BaseModel] = ReadEmailInput
    required_scopes: ClassVar[List[str]] = ['https://www.googleapis.com/auth/gmail.readonly']
    
    def _run(self, query: str = "", max_results: int = 10) -> str:
        """Read/search emails using Gmail API."""
        print(f"Executing function _run from c:\\Users\\vijay\\Documents\\Agentic AI\\AutoAgent\\app\\tools\\gmail_tools.py:103")
        try:
            # Get authenticated credentials
            credentials = self.get_credentials()
            if not credentials:
                return "Failed to authenticate with Google Gmail. Please reconnect your Google account."
            
            # Build Gmail service
            service = build('gmail', 'v1', credentials=credentials)
            
            # Search for messages
            results = service.users().messages().list(
                userId='me',
                q=query,
                maxResults=max_results
            ).execute()
            
            messages = results.get('messages', [])
            
            if not messages:
                return f"No emails found matching query: '{query}'"
            
            # Get details for each message
            email_summaries = []
            for msg in messages[:max_results]:
                # Get full message details including body
                msg_detail = service.users().messages().get(
                    userId='me',
                    id=msg['id'],
                    format='full'  # Changed from 'metadata' to 'full' to get body
                ).execute()
                
                # Extract headers
                headers = msg_detail['payload'].get('headers', [])
                header_dict = {h['name']: h['value'] for h in headers}
                
                # Extract body content
                body_content = self._extract_email_body(msg_detail['payload'])
                
                email_summaries.append({
                    'id': msg['id'],
                    'from': header_dict.get('From', 'Unknown'),
                    'subject': header_dict.get('Subject', 'No Subject'),
                    'date': header_dict.get('Date', 'Unknown'),
                    'body': body_content
                })
            
            # Format response
            result = f"Found {len(email_summaries)} emails:\n"
            for i, email in enumerate(email_summaries, 1):
                result += f"{i}. From: {email['from']}\n"
                result += f"   Subject: {email['subject']}\n"
                result += f"   Body: {email['body']}\n"
                result += f"   Date: {email['date']}\n\n"
            
            return result
            
        except Exception as e:
            return self.handle_api_error(e, "reading emails")

    def _extract_email_body(self, payload) -> str:
        """Extract email body content from Gmail API payload."""
        print(f"Executing function _extract_email_body from c:\\Users\\vijay\\Documents\\Agentic AI\\AutoAgent\\app\\tools\\gmail_tools.py:165")
        
        body = ""
        
        # Handle multipart messages
        if 'parts' in payload:
            for part in payload['parts']:
                if part['mimeType'] == 'text/plain':
                    if 'data' in part['body']:
                        body_data = part['body']['data']
                        body = base64.urlsafe_b64decode(body_data).decode('utf-8')
                        break
                elif part['mimeType'] == 'text/html' and not body:
                    # Fallback to HTML if no plain text
                    if 'data' in part['body']:
                        body_data = part['body']['data']
                        body = base64.urlsafe_b64decode(body_data).decode('utf-8')
                elif 'parts' in part:
                    # Recursively check nested parts
                    body = self._extract_email_body(part)
                    if body:
                        break
        
        # Handle single part messages
        elif payload['mimeType'] == 'text/plain':
            if 'data' in payload['body']:
                body_data = payload['body']['data']
                body = base64.urlsafe_b64decode(body_data).decode('utf-8')
        
        elif payload['mimeType'] == 'text/html':
            if 'data' in payload['body']:
                body_data = payload['body']['data']
                body = base64.urlsafe_b64decode(body_data).decode('utf-8')
        
        # Clean up and truncate body for display
        if body:
            # Remove excessive whitespace and newlines
            body = ' '.join(body.split())
            # Truncate if too long (keep first 200 characters)
            if len(body) > 200:
                body = body[:200] + "..."
            return body
        
        return "<No Body>"
    
    
    async def _arun(self, query: str = "", max_results: int = 10) -> str:
        """Async version - currently just calls sync version."""
        print(f"Executing function _arun from c:\\Users\\vijay\\Documents\\Agentic AI\\AutoAgent\\app\\tools\\gmail_tools.py:159")
        return self._run(query, max_results)
