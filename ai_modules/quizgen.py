from ai_modules.gemini_config import generate_response

def generate_quiz(content, num_questions=5):
    try:
        num = int(num_questions) if num_questions else 5
    except Exception:
        num = 5
    prompt = (
        f"Create {num} multiple-choice questions (with correct answer labeled) from this content. "
        f"Return plain text with clear numbering and options A-D.\n\n{content}"
    )
    return generate_response(prompt)
