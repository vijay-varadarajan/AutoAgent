from fastapi import APIRouter, Request, HTTPException
import requests
import os
from app.config import GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET
from app.services.firestore_db import save_google_tokens, get_pending_workflows
from app.services.enhanced_workflow_executor import EnhancedWorkflowExecutor
import asyncio
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

REDIRECT_URI = "http://localhost:8000/api/oauth/callback"

@router.get("/oauth/callback")
async def oauth_callback(request: Request):
    code = request.query_params.get("code")
    state = request.query_params.get("state")
    if not code:
        raise HTTPException(status_code=400, detail="Missing code")

    # Exchange code for tokens
    token_url = "https://oauth2.googleapis.com/token"
    data = {
        "code": code,
        "client_id": GOOGLE_CLIENT_ID,
        "client_secret": GOOGLE_CLIENT_SECRET,
        "redirect_uri": REDIRECT_URI,
        "grant_type": "authorization_code"
    }
    resp = requests.post(token_url, data=data)
    if resp.status_code != 200:
        return {"error": "Failed to get token", "details": resp.text}
    tokens = resp.json()

    print(f"Received tokens for user {state}: {tokens}")
    # You can store tokens here, e.g., in Firestore, using 'state' as the user_id
    save_google_tokens(state, tokens)
    print(f"Tokens saved for user {state}")
    
    try:
        pending_workflows = get_pending_workflows(state)
        logger.info(f"Found {len(pending_workflows)} pending workflows for user {state}")
        
        if pending_workflows:
            # Execute the most recent pending workflow with background messaging
            latest_workflow = max(pending_workflows, key=lambda w: w.get('created_at', ''))
            workflow_id = latest_workflow.get('workflow_id') or latest_workflow.get('id')
            
            if workflow_id:
                logger.info(f"Triggering background execution of workflow {workflow_id}")
                
                # Create executor without telegram_update (will use background messaging)
                executor = EnhancedWorkflowExecutor(workflow_id, telegram_update=None)
                if executor.load_workflow():
                    # Execute in background with thinking messages
                    asyncio.create_task(executor.execute_workflow())
                    logger.info(f"Background workflow {workflow_id} execution started with thinking messages")
                else:
                    logger.error(f"Failed to load workflow {workflow_id}")
    except Exception as e:
        logger.error(f"Error triggering pending workflows: {e}")

    
    return {
        "status": "success", 
        "message": "Authorization completed! Your workflow will now execute.",
        "redirect": "telegram://resolve"  # This will redirect back to Telegram
    }