from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
import firebase_admin
from firebase_admin import credentials, firestore

# AI modules
from ai_modules.chatbot import ask_chatbot
from ai_modules.summarizer import summarize_notes
from ai_modules.quizgen import generate_quiz

# Flask app setup
app = Flask(__name__)
CORS(app)

# 🔹 Initialize Firestore
cred = credentials.Certificate("firebase-key.json")  # Path to your service key  # Path to your service key
firebase_admin.initialize_app(cred)
db = firestore.client()

@app.route('/')
def home():
    return render_template('index.html')

# ---------------- FIRESTORE ROUTES ----------------

# Get all students
@app.route('/students', methods=['GET'])
def get_students():
    students_ref = db.collection('users').where('user_type', '==', 'student').stream()
    students = [{**doc.to_dict(), "id": doc.id} for doc in students_ref]
    return jsonify(students)

# Get all placement officers
@app.route('/officers', methods=['GET'])
def get_officers():
    officers_ref = db.collection('users').where('user_type', '==', 'placement_officer').stream()
    officers = [{**doc.to_dict(), "id": doc.id} for doc in officers_ref]
    return jsonify(officers)

# Add a new student
@app.route('/add_student', methods=['POST'])
def add_student():
    data = request.get_json()
    db.collection('users').add(data)
    return jsonify({"message": "Student added successfully!"})

# ---------------- AI ROUTES ----------------

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
