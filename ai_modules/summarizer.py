from ai_modules.gemini_config import generate_response

def summarize_notes(notes_text):
    prompt = f"Create:\n\n{notes_text}"
    return generate_response(prompt)
# Summarize the following notes in clear, concise bullet points