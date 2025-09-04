from ai_modules.gemini_config import generate_response

def ask_chatbot(user_query):
    return generate_response(f"Answer this query as a helpful assistant: {user_query}")
