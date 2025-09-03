import firebase_admin
from firebase_admin import credentials, firestore

# Load Firebase key
cred = credentials.Certificate("firebase-key.json")

# Initialize Firebase only once
if not firebase_admin._apps:
    firebase_admin.initialize_app(cred)

# Firestore client
db = firestore.client()
