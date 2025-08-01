from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
from ai_modules.chatbot import ask_chatbot
from ai_modules.summarizer import summarize_notes
from ai_modules.quizgen import generate_quiz

app = Flask(__name__)
CORS(app)

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/askai', methods=['POST'])
def chatbot_api():
    data = request.get_json()
    prompt = data.get('prompt', '')
    return jsonify({'response': ask_chatbot(prompt)})

@app.route('/summarize', methods=['POST'])
def summarize_api():
    data = request.get_json()
    text = data.get('text', '')
    return jsonify({'summary': summarize_notes(text)})

@app.route('/quiz', methods=['POST'])
def quiz_api():
    data = request.get_json()
    text = data.get('text', '')
    return jsonify({'quiz': generate_quiz(text)})

if __name__ == '__main__':
    app.run(debug=True)
