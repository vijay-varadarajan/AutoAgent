from fastapi import APIRouter, Request, HTTPException
import requests
import os
from app.config import GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET
from app.services.firestore_db import save_google_tokens

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

    return {"status": "success", "tokens": tokens}