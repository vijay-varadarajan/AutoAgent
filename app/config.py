import os, json
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
TELEGRAM_BOT_API_KEY = os.getenv("TELEGRAM_BOT_API_KEY")
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")

import firebase_admin
from firebase_admin import credentials, firestore

def initialize_firebase():
    """Initialize Firebase using mounted secret from Cloud Run."""
    try:
        if not firebase_admin._apps:
            # Check for mounted secret first (Cloud Run)
            secret_paths = [
                "/secrets/service-account-key",  # Common mount path
                "/secrets/service-account-key/serviceAccountKey.json",  # If you specified filename
                "/run/secrets/service-account-key",  # Alternative mount path
            ]
            
            service_account_path = None
            for path in secret_paths:
                if os.path.exists(path):
                    service_account_path = path
                    break
            
            if service_account_path:
                print(f"Using service account from: {service_account_path}")
                cred = credentials.Certificate(service_account_path)
                firebase_admin.initialize_app(cred)
            elif os.path.exists("serviceAccountKey.json"):
                # Fallback for local development
                print("Using local serviceAccountKey.json")
                cred = credentials.Certificate("serviceAccountKey.json")
                firebase_admin.initialize_app(cred)
            else:
                # Use default credentials
                print("Using default credentials")
                firebase_admin.initialize_app()
        
        return firestore.client()
    except Exception as e:
        print(f"Error initializing Firebase: {e}")
        return None

db = initialize_firebase()