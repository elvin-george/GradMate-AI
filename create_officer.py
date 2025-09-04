#!/usr/bin/env python3
"""
Create Placement Officer Account Script
Run this script to manually create a placement officer account in Firestore
"""

import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime
import getpass

def create_officer_account():
    """Create a placement officer account manually"""
    
    print("🔐 Creating Placement Officer Account")
    print("=" * 50)
    
    # Initialize Firebase
    try:
        cred = credentials.Certificate("firebase-key.json")
        firebase_admin.initialize_app(cred)
        db = firestore.client()
        print("✅ Firebase initialized successfully")
    except Exception as e:
        print(f"❌ Error initializing Firebase: {e}")
        return
    
    # Get officer details
    print("\n📝 Enter Officer Details:")
    name = input("Full Name: ").strip()
    email = input("Email: ").strip()
    
    # Get password securely
    while True:
        password = getpass.getpass("Password: ")
        confirm_password = getpass.getpass("Confirm Password: ")
        
        if password == confirm_password:
            if len(password) >= 6:
                break
            else:
                print("❌ Password must be at least 6 characters long")
        else:
            print("❌ Passwords don't match")
    
    # Check if email already exists
    try:
        existing_user = db.collection('users').where('email', '==', email).limit(1).stream()
        if list(existing_user):
            print(f"❌ Email {email} is already registered")
            return
    except Exception as e:
        print(f"⚠️  Warning: Could not check existing users: {e}")
    
    # Create officer data
    officer_data = {
        'name': name,
        'email': email,
        'password': password,  # In production, hash this password
        'user_type': 'placement_officer',
        'created_at': datetime.now()
    }
    
    try:
        # Add officer to database
        doc_ref = db.collection('users').add(officer_data)
        officer_data['id'] = doc_ref[1].id
        
        print("\n✅ Placement Officer Account Created Successfully!")
        print("=" * 50)
        print(f"ID: {officer_data['id']}")
        print(f"Name: {officer_data['name']}")
        print(f"Email: {officer_data['email']}")
        print(f"User Type: {officer_data['user_type']}")
        print(f"Created: {officer_data['created_at']}")
        print("\n🔑 The officer can now log in using these credentials")
        print("⚠️  Remember to change the password after first login in production")
        
    except Exception as e:
        print(f"❌ Error creating officer account: {e}")

if __name__ == '__main__':
    try:
        create_officer_account()
    except KeyboardInterrupt:
        print("\n\n👋 Operation cancelled by user")
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
    
    input("\nPress Enter to exit...") 