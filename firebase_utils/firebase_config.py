import os
import firebase_admin
from firebase_admin import credentials, firestore

# Third-party client for email/password auth
try:
    import pyrebase
except Exception:
    pyrebase = None

# Load Firebase Admin key for server-side access
cred = credentials.Certificate("firebase-key.json")

# Initialize Firebase Admin only once (used for Firestore and verifying tokens)
if not firebase_admin._apps:
    firebase_admin.initialize_app(cred)

# Firestore client (admin SDK)
db = firestore.client()

# Initialize Pyrebase for client-side auth flows (email/password)
pyrebase_config = {
    "apiKey": os.getenv("FIREBASE_WEB_API_KEY", ""),
    "authDomain": os.getenv("FIREBASE_AUTH_DOMAIN", ""),
    "projectId": os.getenv("FIREBASE_PROJECT_ID", ""),
    "storageBucket": os.getenv("FIREBASE_STORAGE_BUCKET", ""),
    "messagingSenderId": os.getenv("FIREBASE_MESSAGING_SENDER_ID", ""),
    "appId": os.getenv("FIREBASE_APP_ID", ""),
    # Realtime DB URL optional if not used
    "databaseURL": os.getenv("FIREBASE_DATABASE_URL", "")
}

if pyrebase is not None:
    try:
        _pb_app = pyrebase.initialize_app(pyrebase_config)
        auth = _pb_app.auth()
    except Exception:
        # Fallback: leave auth undefined if config is missing; routes should handle gracefully
        auth = None
else:
    auth = None

