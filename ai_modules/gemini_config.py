import os
from dotenv import load_dotenv
import google.generativeai as genai

# Load environment variables from .env file
load_dotenv()

# Get the API key from the environment
API_KEY = os.getenv("GEMINI_API_KEY")

# Configure the generative AI client
genai.configure(api_key=API_KEY)

# Define a helper function to generate responses
def generate_response(prompt, model="gemini-1.5-flash"):
    try:
        model = genai.GenerativeModel(model)
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"Error: {e}"

# Generate study plan title
def generate_title(study_request):
    try:
        prompt = f"Generate a concise, descriptive title for this study plan request: {study_request}. Return only the title, no additional text."
        title = generate_response(prompt)
        return title.strip() if title and not title.startswith("Error:") else "Study Plan"
    except Exception as e:
        return "Study Plan"