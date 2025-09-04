#!/usr/bin/env python3
"""
GradMate AI - Startup Script
Run this file to start the GradMate AI application
"""

import os
import sys
from dotenv import load_dotenv

def check_requirements():
    """Check if all required files and configurations are present"""
    required_files = [
        'app.py',
        'firebase-key.json',
        'requirements.txt'
    ]
    
    missing_files = []
    for file in required_files:
        if not os.path.exists(file):
            missing_files.append(file)
    
    if missing_files:
        print("❌ Missing required files:")
        for file in missing_files:
            print(f"   - {file}")
        print("\nPlease ensure all required files are present before running the application.")
        return False
    
    return True

def check_environment():
    """Check environment configuration"""
    load_dotenv()
    
    if not os.getenv('GEMINI_API_KEY'):
        print("⚠️  Warning: GEMINI_API_KEY not found in environment variables")
        print("   Create a .env file with your Gemini API key:")
        print("   GEMINI_API_KEY=your_api_key_here")
        print("\n   You can still run the app, but AI features won't work.")
    
    return True

def main():
    """Main startup function"""
    print("🚀 Starting GradMate AI...")
    print("=" * 50)
    
    # Check requirements
    if not check_requirements():
        sys.exit(1)
    
    # Check environment
    check_environment()
    
    print("✅ All checks passed!")
    print("🌐 Starting Flask application...")
    print("📱 Open your browser and go to: http://localhost:5000")
    print("⏹️  Press Ctrl+C to stop the application")
    print("=" * 50)
    
    try:
        # Import and run the Flask app
        from app import app
        app.run(debug=True, host='0.0.0.0', port=5000)
    except KeyboardInterrupt:
        print("\n👋 GradMate AI stopped. Goodbye!")
    except Exception as e:
        print(f"\n❌ Error starting application: {e}")
        print("Please check your configuration and try again.")
        sys.exit(1)

if __name__ == '__main__':
    main() 