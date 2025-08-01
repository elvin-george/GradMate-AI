from ai_modules.gemini_config import generate_response

def generate_quiz(content):
    prompt = f"Create 5 multiple-choice questions (with answers) from this content:\n\n{content}"
    return generate_response(prompt)
