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

# Generate study tasks in strict JSON format
def generate_tasks_json(study_request, num_tasks=5):
    try:
        system_prompt = (
            "You are an assistant that outputs ONLY valid JSON with no code fences. "
            "Return an array named tasks of task objects. Each task must have: "
            "task (string), due_date (ISO 8601 string, e.g., 2025-01-31T17:00:00Z), status (string: 'pending'). "
            "Example: {\"tasks\":[{\"task\":\"Revise chapter 1\",\"due_date\":\"2025-01-01T17:00:00Z\",\"status\":\"pending\"}]}"
        )
        prompt = (
            f"{system_prompt}\n\n"
            f"Create {num_tasks} study tasks for this request: {study_request}. "
            f"Distribute due_date over the next 7 days."
        )
        raw = generate_response(prompt)
        return raw
    except Exception as e:
        return f"Error: {e}"