from flask import Flask, render_template, request, jsonify, redirect, url_for, session, flash
from flask_cors import CORS
import firebase_admin
from firebase_admin import credentials, firestore, auth as admin_auth
import uuid
from datetime import datetime, timedelta, timezone
import json
import os
import requests
from dotenv import load_dotenv

# AI modules
from ai_modules.chatbot import ask_chatbot
from ai_modules.summarizer import summarize_notes
from ai_modules.quizgen import generate_quiz
from ai_modules.gemini_config import generate_tasks_json

# Flask app setup
load_dotenv()

app = Flask(__name__)
app.secret_key = 'gradmate_ai_secret_key_2024'  # Change this in production
CORS(app)

# 🔹 Initialize Firestore (Admin SDK)
cred = credentials.Certificate("firebase-key.json")
if not firebase_admin._apps:
    firebase_admin.initialize_app(cred)
db = firestore.client()

# 🔹 Pyrebase auth (for email/password sign-in)
try:
    from firebase_utils.firebase_config import auth as pyre_auth
except Exception:
    pyre_auth = None

# Expose Firebase Web SDK config and current user to templates
@app.context_processor
def inject_firebase_web_config():
    web_config = {
        'apiKey': os.getenv('FIREBASE_WEB_API_KEY', ''),
        'authDomain': os.getenv('FIREBASE_AUTH_DOMAIN', ''),
        'projectId': os.getenv('FIREBASE_PROJECT_ID', ''),
        'storageBucket': os.getenv('FIREBASE_STORAGE_BUCKET', ''),
        'messagingSenderId': os.getenv('FIREBASE_MESSAGING_SENDER_ID', ''),
        'appId': os.getenv('FIREBASE_APP_ID', ''),
        'databaseURL': os.getenv('FIREBASE_DATABASE_URL', '')
    }
    return {
        'FIREBASE_WEB_CONFIG': web_config,
        'CURRENT_USER_ID': session.get('user_id')
    }

# Session configuration
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=24)

# Helper function to check if user is logged in
def is_logged_in():
    return 'user_id' in session

# Helper function to get current user
def get_current_user():
    if is_logged_in():
        user_doc = db.collection('users').document(session['user_id']).get()
        if user_doc.exists:
            user_data = user_doc.to_dict()
            user_data['id'] = user_doc.id  # Keep 'id' for backward compatibility
            return user_data
    return None

# Helper function to require login
def get_valid_id_token():
    id_token = session.get('idToken')
    refresh_token = session.get('refreshToken')
    if not refresh_token:
        return None
    # Verify current token
    try:
        if id_token:
            admin_auth.verify_id_token(id_token)
            return id_token
    except Exception:
        pass
    # Refresh if needed
    try:
        if pyre_auth is not None and refresh_token:
            refreshed = pyre_auth.refresh(refresh_token)
            session['idToken'] = refreshed.get('idToken') or refreshed.get('id_token')
            return session.get('idToken')
    except Exception:
        return None
    return None

def login_required(f):
    def decorated_function(*args, **kwargs):
        if not is_logged_in():
            return redirect(url_for('login'))
        token = get_valid_id_token()
        if not token:
            session.clear()
            return redirect(url_for('login'))
        try:
            decoded = admin_auth.verify_id_token(token)
            request.uid = decoded.get('uid')
        except Exception:
            session.clear()
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    decorated_function.__name__ = f.__name__
    return decorated_function

# Helper function to require specific user type
def require_user_type(user_type):
    def decorator(f):
        def decorated_function(*args, **kwargs):
            if not is_logged_in():
                return redirect(url_for('login'))
            user = get_current_user()
            if user and user.get('user_type') == user_type:
                return f(*args, **kwargs)
            flash('Access denied. You do not have permission to view this page.', 'error')
            return redirect(url_for('dashboard'))
        decorated_function.__name__ = f.__name__
        return decorated_function
    return decorator

# ==================== AUTHENTICATION ROUTES ====================

@app.route('/')
def home():
    if is_logged_in():
        return redirect(url_for('dashboard'))
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        data = request.get_json() or {}
        email = (data.get('email') or '').strip()
        password = data.get('password') or ''
        user_type = data.get('user_type') or 'student'

        try:
            # Sign in with Firebase Authentication (Pyrebase)
            auth_resp = None
            if pyre_auth is not None:
                auth_resp = pyre_auth.sign_in_with_email_and_password(email, password)
            else:
                # Fallback: REST API
                api_key = os.getenv('FIREBASE_WEB_API_KEY')
                if not api_key:
                    return jsonify({'success': False, 'message': 'Server auth not configured'})
                sign_in_url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={api_key}"
                resp = requests.post(sign_in_url, json={
                    'email': email,
                    'password': password,
                    'returnSecureToken': True
                }, timeout=10)
                if resp.status_code != 200:
                    return jsonify({'success': False, 'message': 'Invalid email or password'})
                auth_resp = resp.json()

            uid = auth_resp.get('localId') or auth_resp.get('userId')
            id_token = auth_resp.get('idToken') or auth_resp.get('id_token')
            refresh_token = auth_resp.get('refreshToken') or auth_resp.get('refresh_token')

            if not uid:
                return jsonify({'success': False, 'message': 'Authentication failed'})

            # Verify user profile and type
            user_doc = db.collection('users').document(uid).get()
            if not user_doc.exists:
                return jsonify({'success': False, 'message': 'User profile not found'})

            user_data = user_doc.to_dict()
            if user_data.get('user_type') != user_type:
                return jsonify({'success': False, 'message': 'Invalid user type for this account'})

            # Set session with tokens
            session['user_id'] = uid
            session['user_type'] = user_data.get('user_type')
            session['user_name'] = user_data.get('name')
            if id_token:
                session['idToken'] = id_token
            if refresh_token:
                session['refreshToken'] = refresh_token

            return jsonify({'success': True, 'redirect': url_for('dashboard')})

        except Exception as e:
            print(f"Login error: {e}")
            return jsonify({'success': False, 'message': 'Invalid email or password'})

    return render_template('login.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        data = request.get_json() or {}
        user_type = data.get('user_type')

        # Only allow student signup - officers must be created manually
        if user_type != 'student':
            return jsonify({'success': False, 'message': 'Only students can sign up. Placement officers are pre-created.'})

        try:
            email = (data.get('email') or '').strip()
            password = data.get('password') or ''
            name = (data.get('name') or '').strip()

            # Create user in Firebase Auth via Pyrebase
            if pyre_auth is None:
                return jsonify({'success': False, 'message': 'Server auth not configured'})

            created = pyre_auth.create_user_with_email_and_password(email, password)
            uid = created.get('localId')

            # Create user profile in Firestore (without password)
            user_data = {
                'uid': uid,
                'name': name,
                'email': email,
                'user_type': 'student',
                'department': data.get('department'),
                'cgpa': float(data.get('cgpa', 0)),
                'skills': data.get('skills', []),
                'resume_url': '',
                'created_at': datetime.now()
            }

            db.collection('users').document(uid).set(user_data)

            # Sign in to get tokens
            auth_resp = pyre_auth.sign_in_with_email_and_password(email, password)
            id_token = auth_resp.get('idToken') or auth_resp.get('id_token')
            refresh_token = auth_resp.get('refreshToken') or auth_resp.get('refresh_token')

            # Session
            session['user_id'] = uid
            session['user_type'] = user_data['user_type']
            session['user_name'] = user_data['name']
            if id_token:
                session['idToken'] = id_token
            if refresh_token:
                session['refreshToken'] = refresh_token

            return jsonify({'success': True, 'redirect': url_for('dashboard')})

        except Exception as e:
            # Handle duplicate email and other errors uniformly
            print(f"Signup error: {e}")
            return jsonify({'success': False, 'message': 'Account creation failed'})

    return render_template('signup.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))

# ==================== DASHBOARD ROUTES ====================

@app.route('/dashboard')
@login_required
def dashboard():
    user = get_current_user()
    if user['user_type'] == 'student':
        return redirect(url_for('student_dashboard'))
    else:
        return redirect(url_for('officer_dashboard'))

@app.route('/student/dashboard')
@login_required
@require_user_type('student')
def student_dashboard():
    user = get_current_user()
    
    # Get upcoming tasks from study_plans collection (new schema)
    upcoming_tasks = []
    try:
        study_plans_ref = db.collection('study_plans').where('user_id', '==', user['id']).stream()
        for plan_doc in study_plans_ref:
            plan_data = plan_doc.to_dict()
            if 'tasks' in plan_data:
                for task in plan_data['tasks']:
                    if task.get('status') == 'pending':
                        # Normalize due_date to datetime or None
                        raw_due = task.get('due_date')
                        parsed_due = None
                        if isinstance(raw_due, str):
                            try:
                                parsed_due = datetime.strptime(raw_due.strip(), '%Y-%m-%d')
                            except Exception:
                                parsed_due = None
                        elif hasattr(raw_due, 'isoformat'):
                            # Firestore Timestamp or datetime
                            try:
                                parsed_due = raw_due
                            except Exception:
                                parsed_due = None

                        upcoming_tasks.append({
                            'id': f"{plan_doc.id}_{task.get('task', '')}",
                            'title': task.get('task', ''),
                            'due_date': parsed_due,
                            'status': task.get('status', 'pending')
                        })
        
        # Sort by due date (None last) and limit to 5
        upcoming_tasks.sort(key=lambda x: (x.get('due_date') is None, x.get('due_date') or datetime.max))
        upcoming_tasks = upcoming_tasks[:5]
        
    except Exception as e:
        # Handle index errors gracefully
        print(f"Error fetching tasks: {e}")
        upcoming_tasks = []
    
    # Get placement drives
    upcoming_drives = []
    try:
        drives_ref = db.collection('placement_drives').stream()
        for doc in drives_ref:
            drive_data = doc.to_dict()
            # Check if drive is still open for applications
            if 'last_date_to_apply' in drive_data:
                last_date = drive_data['last_date_to_apply']
                if isinstance(last_date, str):
                    from datetime import datetime
                    try:
                        last_date = datetime.fromisoformat(last_date.replace('Z', '+00:00'))
                    except:
                        last_date = datetime.now()
                
                if last_date > datetime.now(timezone.utc):
                    # Add template-friendly aliases while keeping schema
                    alias = {**drive_data, 'id': doc.id}
                    alias['position'] = drive_data.get('job_role')
                    # Normalize deadline to datetime or None for template strftime
                    deadline_raw = drive_data.get('last_date_to_apply')
                    deadline_dt = None
                    if isinstance(deadline_raw, str):
                        try:
                            deadline_dt = datetime.fromisoformat(deadline_raw.replace('Z', '+00:00'))
                        except Exception:
                            deadline_dt = None
                    elif hasattr(deadline_raw, 'isoformat'):
                        try:
                            deadline_dt = deadline_raw
                        except Exception:
                            deadline_dt = None
                    alias['deadline'] = deadline_dt
                    elig = drive_data.get('eligibility_criteria') or {}
                    alias['min_cgpa'] = (elig.get('cgpa') if isinstance(elig, dict) else None)
                    alias['departments'] = (elig.get('departments') if isinstance(elig, dict) else [])
                    alias['requirements'] = drive_data.get('skills_required', [])
                    upcoming_drives.append(alias)
        
        upcoming_drives = upcoming_drives[:3]
        
    except Exception as e:
        print(f"Error fetching drives: {e}")
        upcoming_drives = []
    
    return render_template('student_dashboard.html', user=user, upcoming_tasks=upcoming_tasks, upcoming_drives=upcoming_drives)

@app.route('/officer/dashboard')
@login_required
@require_user_type('placement_officer')
def officer_dashboard():
    user = get_current_user()
    
    # Get posted drives count
    drives_count = 0
    try:
        drives_count = len(list(db.collection('placement_drives').where('posted_by', '==', user['id']).stream()))
    except Exception as e:
        print(f"Error fetching drives count: {e}")
    
    # Get active students count
    students_count = 0
    try:
        students_count = len(list(db.collection('users').where('user_type', '==', 'student').stream()))
    except Exception as e:
        print(f"Error fetching students count: {e}")
    
    # Get recent applications
    recent_applications = []
    try:
        # Get drives posted by this officer
        officer_drives = []
        drives_ref = db.collection('placement_drives').where('posted_by', '==', user['id']).stream()
        for doc in drives_ref:
            officer_drives.append(doc.id)
        
        if officer_drives:
            # Get applications for these drives
            applications_ref = db.collection('applications').stream()
            for doc in applications_ref:
                app_data = doc.to_dict()
                if app_data.get('drive_id') in officer_drives:
                    student_doc = db.collection('users').document(app_data['student_id']).get()
                    if student_doc.exists:
                        app_data['student_name'] = student_doc.to_dict()['name']
                        app_data['id'] = doc.id
                        # Normalize applied_at to datetime or None
                        applied_raw = app_data.get('applied_at')
                        if isinstance(applied_raw, str):
                            try:
                                app_data['applied_at'] = datetime.fromisoformat(applied_raw.replace('Z', '+00:00'))
                            except Exception:
                                app_data['applied_at'] = None
                        elif hasattr(applied_raw, 'isoformat'):
                            try:
                                app_data['applied_at'] = applied_raw
                            except Exception:
                                app_data['applied_at'] = None
                        else:
                            app_data['applied_at'] = None
                        recent_applications.append(app_data)
        
        # Sort by applied_at (None last) and limit to 5
        recent_applications.sort(key=lambda x: (x.get('applied_at') is None, x.get('applied_at') or datetime.min), reverse=True)
        recent_applications = recent_applications[:5]
        
    except Exception as e:
        print(f"Error fetching applications: {e}")
    
    return render_template('officer_dashboard.html', user=user, drives_count=drives_count, students_count=students_count, recent_applications=recent_applications)

# ==================== STUDENT FEATURE ROUTES ====================

@app.route('/student/chatbot')
@login_required
@require_user_type('student')
def student_chatbot():
    user = get_current_user()
    return render_template('student_chatbot.html', user=user)

@app.route('/student/summarizer')
@login_required
@require_user_type('student')
def student_summarizer():
    user = get_current_user()
    return render_template('student_summarizer.html', user=user)

@app.route('/student/quizgen')
@login_required
@require_user_type('student')
def student_quizgen():
    user = get_current_user()
    return render_template('student_quizgen.html', user=user)

@app.route('/student/studyplanner')
@login_required
@require_user_type('student')
def student_studyplanner():
    user = get_current_user()
    
    # Get all tasks for the user (removed order_by to avoid index requirement)
    # Note: If ordering by due_date is required, create composite index: user_id (Ascending), due_date (Ascending)
    tasks_ref = db.collection('study_plans').where('user_id', '==', user['id']).stream()
    tasks = []
    for plan_doc in tasks_ref:
        plan_data = plan_doc.to_dict()
        if 'tasks' in plan_data:
            for task in plan_data['tasks']:
                # Normalize due_date to datetime or None
                raw_due = task.get('due_date')
                parsed_due = None
                if isinstance(raw_due, str):
                    try:
                        parsed_due = datetime.strptime(raw_due.strip(), '%Y-%m-%d')
                    except Exception:
                        parsed_due = None
                elif hasattr(raw_due, 'isoformat'):
                    try:
                        parsed_due = raw_due
                    except Exception:
                        parsed_due = None
                tasks.append({
                    'id': f"{plan_doc.id}_{task.get('task', '')}",
                    'title': task.get('task', ''),
                    'due_date': parsed_due,
                    'status': task.get('status', 'pending'),
                    'plan_id': plan_doc.id,
                    'priority': 'medium',
                    'description': '',
                    'completed': task.get('status', 'pending') in ['done', 'completed']
                })
    
    # Sort in Python to avoid Firestore index requirement (None last)
    tasks.sort(key=lambda x: (x.get('due_date') is None, x.get('due_date') or datetime.max))
    
    return render_template('student_studyplanner.html', user=user, tasks=tasks)

@app.route('/student/resume')
@login_required
@require_user_type('student')
def student_resume():
    user = get_current_user()
    return render_template('student_resume.html', user=user)

@app.route('/student/placements')
@login_required
@require_user_type('student')
def student_placements():
    user = get_current_user()
    
    # Get all placement drives (removed order_by to avoid index requirement)
    # Note: If ordering by date is required, create composite index: active (Ascending), date (Ascending)
    drives_ref = db.collection('placement_drives').stream()
    drives = []
    for doc in drives_ref:
        drive_data = doc.to_dict()
        # Check if drive is still open for applications
        if 'last_date_to_apply' in drive_data:
            last_date = drive_data['last_date_to_apply']
            if isinstance(last_date, str):
                try:
                    last_date = datetime.fromisoformat(last_date.replace('Z', '+00:00'))
                except:
                    last_date = datetime.now()
            
            if last_date > datetime.now(timezone.utc):
                alias = {**drive_data, 'id': doc.id}
                alias['position'] = drive_data.get('job_role')
                alias['deadline'] = drive_data.get('last_date_to_apply')
                elig = drive_data.get('eligibility_criteria') or {}
                alias['min_cgpa'] = (elig.get('cgpa') if isinstance(elig, dict) else None)
                alias['departments'] = (elig.get('departments') if isinstance(elig, dict) else [])
                alias['requirements'] = drive_data.get('skills_required', [])
                drives.append(alias)
    
    # Sort in Python to avoid Firestore index requirement
    drives.sort(key=lambda x: x.get('last_date_to_apply', ''))
    
    # Get training materials (removed order_by to avoid index requirement)
    # Note: If ordering by upload_date is required, create composite index: upload_date (Ascending)
    training_ref = db.collection('training_resources').stream()
    training_materials = []
    for tdoc in training_ref:
        tdata = tdoc.to_dict()
        alias = {**tdata, 'id': tdoc.id}
        alias['type'] = tdata.get('resource_type')
        alias['link'] = tdata.get('resource_url')
        if 'description' not in alias:
            tags = tdata.get('tags') or []
            alias['description'] = ', '.join(tags) if tags else ''
        training_materials.append(alias)
    
    # Sort in Python to avoid Firestore index requirement
    training_materials.sort(key=lambda x: x.get('upload_date', ''), reverse=True)
    
    return render_template('student_placements.html', user=user, drives=drives, training_materials=training_materials)

@app.route('/student/messages')
@login_required
@require_user_type('student')
def student_messages():
    user = get_current_user()
    
    # Get all users for chat
    users_ref = db.collection('users').stream()
    users = [{**doc.to_dict(), 'id': doc.id} for doc in users_ref if doc.id != user['id']]
    
    return render_template('student_messages.html', user=user, users=users)

# ==================== OFFICER FEATURE ROUTES ====================

@app.route('/officer/drives')
@login_required
@require_user_type('placement_officer')
def officer_drives():
    user = get_current_user()
    
    # Get all drives posted by this officer (removed order_by to avoid index requirement)
    # Note: If ordering by created_at is required, create composite index: posted_by (Ascending), created_at (Ascending)
    drives_ref = db.collection('placement_drives').where('posted_by', '==', user['id']).stream()
    drives = [{**doc.to_dict(), 'id': doc.id} for doc in drives_ref]
    
    # Sort in Python to avoid Firestore index requirement
    drives.sort(key=lambda x: x.get('created_at', ''), reverse=True)
    
    return render_template('officer_drives.html', user=user, drives=drives)

@app.route('/officer/training')
@login_required
@require_user_type('placement_officer')
def officer_training():
    user = get_current_user()
    
    # Get all training materials posted by this officer (removed order_by to avoid index requirement)
    # Note: If ordering by upload_date is required, create composite index: uploaded_by (Ascending), upload_date (Ascending)
    materials_ref = db.collection('training_resources').where('uploaded_by', '==', user['id']).stream()
    materials = [{**doc.to_dict(), 'id': doc.id} for doc in materials_ref]
    
    # Sort in Python to avoid Firestore index requirement
    materials.sort(key=lambda x: x.get('upload_date', ''), reverse=True)
    
    return render_template('officer_training.html', user=user, materials=materials)

@app.route('/officer/filter')
@login_required
@require_user_type('placement_officer')
def officer_filter():
    user = get_current_user()
    
    # Get all students
    students_ref = db.collection('users').where('user_type', '==', 'student').stream()
    students = [{**doc.to_dict(), 'id': doc.id} for doc in students_ref]
    
    return render_template('officer_filter.html', user=user, students=students)

@app.route('/officer/messages')
@login_required
@require_user_type('placement_officer')
def officer_messages():
    user = get_current_user()
    
    # Get all users for chat
    users_ref = db.collection('users').stream()
    users = [{**doc.to_dict(), 'id': doc.id} for doc in users_ref if doc.id != user['id']]
    
    return render_template('officer_messages.html', user=user, users=users)

# ==================== API ENDPOINTS ====================

@app.route('/api/chatbot', methods=['POST'])
@login_required
def chatbot_api():
    user = get_current_user()
    data = request.get_json()
    prompt = data.get('prompt', '')
    response = ask_chatbot(prompt)
    
    # Track AI usage
    try:
        ai_usage_data = {
            'user_id': user['id'],
            'tool_used': 'chatbot',
            'timestamp': datetime.now(),
            'input_summary': prompt[:100] + '...' if len(prompt) > 100 else prompt,
            'ai_response': response[:200] + '...' if len(response) > 200 else response
        }
        db.collection('ai_usage').add(ai_usage_data)
    except Exception as e:
        print(f"Error tracking AI usage: {e}")
    
    return jsonify({'response': response})

@app.route('/api/summarize', methods=['POST'])
@login_required
def summarize_api():
    user = get_current_user()
    data = request.get_json()
    text = data.get('text', '')
    summary = summarize_notes(text)
    
    # Track AI usage
    try:
        ai_usage_data = {
            'user_id': user['id'],
            'tool_used': 'summarizer',
            'timestamp': datetime.now(),
            'input_summary': text[:100] + '...' if len(text) > 100 else text,
            'ai_response': summary[:200] + '...' if len(summary) > 200 else summary
        }
        db.collection('ai_usage').add(ai_usage_data)
    except Exception as e:
        print(f"Error tracking AI usage: {e}")
    
    return jsonify({'summary': summary})

@app.route('/api/quizgen', methods=['POST'])
@login_required
def quiz_api():
    user = get_current_user()
    data = request.get_json()
    text = data.get('text', '')
    num_questions = data.get('num_questions', 5)
    quiz = generate_quiz(text, num_questions)
    
    # Track AI usage
    try:
        ai_usage_data = {
            'user_id': user['id'],
            'tool_used': 'quizgen',
            'timestamp': datetime.now(),
            'input_summary': text[:100] + '...' if len(text) > 100 else text,
            'ai_response': quiz[:200] + '...' if len(quiz) > 200 else quiz
        }
        db.collection('ai_usage').add(ai_usage_data)
    except Exception as e:
        print(f"Error tracking AI usage: {e}")
    
    return jsonify({'quiz': quiz})

# ==================== STUDY PLANNER AI TASK GENERATION ====================

@app.route('/api/studyplan/generate', methods=['POST'])
@login_required
@require_user_type('student')
def generate_study_tasks():
    user = get_current_user()
    data = request.get_json() or {}
    study_request = data.get('request') or ''
    num_tasks = data.get('num_tasks', 5)

    # Ask Gemini to produce strict JSON
    raw = generate_tasks_json(study_request, num_tasks)

    # Parse JSON safely
    try:
        parsed = json.loads(raw)
        tasks = parsed.get('tasks') or []
    except Exception:
        return jsonify({'error': 'Failed to parse AI response'}), 400

    if not isinstance(tasks, list) or not tasks:
        return jsonify({'error': 'No tasks generated'}), 400

    # Upsert a single study plan for the user
    existing_plans = db.collection('study_plans').where('user_id', '==', user['id']).limit(1).stream()
    plan_doc = None
    for doc in existing_plans:
        plan_doc = doc
        break

    if plan_doc:
        plan_data = plan_doc.to_dict()
        if 'tasks' not in plan_data:
            plan_data['tasks'] = []
        # Normalize tasks
        for t in tasks:
            plan_data['tasks'].append({
                'task': t.get('task'),
                'due_date': t.get('due_date'),
                'status': t.get('status') or 'pending'
            })
        db.collection('study_plans').document(plan_doc.id).update(plan_data)
        plan_id = plan_doc.id
    else:
        plan_data = {
            'user_id': user['id'],
            'title': data.get('title') or 'Study Plan',
            'created_on': datetime.now(timezone.utc),
            'tasks': [{
                'task': t.get('task'),
                'due_date': t.get('due_date'),
                'status': t.get('status') or 'pending'
            } for t in tasks]
        }
        doc_ref = db.collection('study_plans').add(plan_data)
        plan_id = doc_ref[1].id

    # Track AI usage
    try:
        db.collection('ai_usage').add({
            'user_id': user['id'],
            'tool_used': 'study_tasks_ai',
            'timestamp': datetime.now(timezone.utc),
            'input_summary': (study_request[:100] + '...') if len(study_request) > 100 else study_request,
            'ai_response': (raw[:200] + '...') if len(raw) > 200 else raw
        })
    except Exception as e:
        print(f"Error tracking AI usage (study tasks): {e}")

    return jsonify({'success': True, 'plan_id': plan_id, 'tasks_added': len(tasks)})

# ==================== STUDY PLANNER API ====================

@app.route('/api/tasks', methods=['GET'])
@login_required
def get_tasks():
    user = get_current_user()
    tasks = []
    
    try:
        # Get tasks from study_plans collection (new schema)
        study_plans_ref = db.collection('study_plans').where('user_id', '==', user['id']).stream()
        for plan_doc in study_plans_ref:
            plan_data = plan_doc.to_dict()
            if 'tasks' in plan_data:
                for task in plan_data['tasks']:
                    tasks.append({
                        'id': f"{plan_doc.id}_{task.get('task', '')}",
                        'title': task.get('task', ''),
                        'due_date': task.get('due_date'),
                        'status': task.get('status', 'pending'),
                        'plan_id': plan_doc.id,
                        'priority': 'medium',
                        'description': '',
                        'completed': task.get('status', 'pending') in ['done', 'completed']
                    })
        
        # Sort by due date
        tasks.sort(key=lambda x: x.get('due_date', ''))
        
    except Exception as e:
        print(f"Error fetching tasks: {e}")
        # Return empty list if index error occurs
        return jsonify([])
    
    return jsonify(tasks)

@app.route('/api/tasks', methods=['POST'])
@login_required
def create_task():
    user = get_current_user()
    data = request.get_json()
    
    # Create or update study plan
    plan_title = data.get('plan_title', 'Study Plan')
    task_title = data.get('title')
    due_date = data.get('due_date')
    
    # Check if user has an existing study plan
    existing_plans = db.collection('study_plans').where('user_id', '==', user['id']).limit(1).stream()
    plan_doc = None
    
    for doc in existing_plans:
        plan_doc = doc
        break
    
    if plan_doc:
        # Update existing plan
        plan_data = plan_doc.to_dict()
        if 'tasks' not in plan_data:
            plan_data['tasks'] = []
        
        plan_data['tasks'].append({
            'task': task_title,
            'due_date': due_date,
            'status': 'pending'
        })
        
        db.collection('study_plans').document(plan_doc.id).update(plan_data)
        plan_id = plan_doc.id
    else:
        # Generate title using Gemini API if not provided
        if not plan_title or plan_title == 'Study Plan':
            try:
                from ai_modules.gemini_config import generate_title
                plan_title = generate_title(f"Study plan for: {task_title}")
            except:
                plan_title = f"Study Plan - {task_title}"
        
        # Create new plan
        plan_data = {
            'user_id': user['id'],
            'title': plan_title,
            'created_on': datetime.now(),
            'tasks': [{
                'task': task_title,
                'due_date': due_date,
                'status': 'pending'
            }]
        }
        
        doc_ref = db.collection('study_plans').add(plan_data)
        plan_id = doc_ref[1].id
    
    return jsonify({
        'id': f"{plan_id}_{task_title}",
        'title': task_title,
        'due_date': due_date,
        'status': 'pending',
        'plan_id': plan_id,
        'priority': 'medium',
        'description': '',
        'completed': False
    })

@app.route('/api/tasks/<task_id>', methods=['PUT'])
@login_required
def update_task(task_id):
    user = get_current_user()
    data = request.get_json()
    
    try:
        # Parse task_id to get plan_id and task_title
        if '_' in task_id:
            plan_id, task_title = task_id.split('_', 1)
        else:
            return jsonify({'error': 'Invalid task ID format'}), 400
        
        # Get the study plan
        plan_doc = db.collection('study_plans').document(plan_id).get()
        if not plan_doc.exists:
            return jsonify({'error': 'Study plan not found'}), 404
        
        plan_data = plan_doc.to_dict()
        if plan_data['user_id'] != user['id']:
            return jsonify({'error': 'Unauthorized'}), 403
        
        # Update the specific task
        if 'tasks' in plan_data:
            for task in plan_data['tasks']:
                if task.get('task') == task_title:
                    task.update(data)
                    break
        
        db.collection('study_plans').document(plan_id).update(plan_data)
        return jsonify({'message': 'Task updated successfully'})
        
    except Exception as e:
        print(f"Error updating task: {e}")
        return jsonify({'error': 'Failed to update task'}), 500

@app.route('/api/tasks/<task_id>', methods=['DELETE'])
@login_required
def delete_task(task_id):
    user = get_current_user()
    
    try:
        # Parse task_id to get plan_id and task_title
        if '_' in task_id:
            plan_id, task_title = task_id.split('_', 1)
        else:
            return jsonify({'error': 'Invalid task ID format'}), 400
        
        # Get the study plan
        plan_doc = db.collection('study_plans').document(plan_id).get()
        if not plan_doc.exists:
            return jsonify({'error': 'Study plan not found'}), 404
        
        plan_data = plan_doc.to_dict()
        if plan_data['user_id'] != user['id']:
            return jsonify({'error': 'Unauthorized'}), 403
        
        # Remove the specific task
        if 'tasks' in plan_data:
            plan_data['tasks'] = [task for task in plan_data['tasks'] if task.get('task') != task_title]
        
        db.collection('study_plans').document(plan_id).update(plan_data)
        return jsonify({'message': 'Task deleted successfully'})
        
    except Exception as e:
        print(f"Error deleting task: {e}")
        return jsonify({'error': 'Failed to delete task'}), 500

# ==================== RESUME API ====================

@app.route('/api/resume', methods=['PUT'])
@login_required
@require_user_type('student')
def update_resume():
    user = get_current_user()
    data = request.get_json()
    resume_url = data.get('resume_url')
    
    db.collection('users').document(user['id']).update({
        'resume_url': resume_url,
        'updated_at': datetime.now()
    })
    
    return jsonify({'message': 'Resume updated successfully'})

# ==================== PLACEMENT DRIVES API ====================

@app.route('/api/drives', methods=['GET'])
@login_required
def get_drives():
    try:
        drives_ref = db.collection('placement_drives').stream()
        drives = []
        for doc in drives_ref:
            drive_data = doc.to_dict()
            # Check if drive is still open for applications
            if 'last_date_to_apply' in drive_data:
                last_date = drive_data['last_date_to_apply']
                if isinstance(last_date, str):
                    try:
                        last_date = datetime.fromisoformat(last_date.replace('Z', '+00:00'))
                    except:
                        last_date = datetime.now()
                
                if last_date > datetime.now(timezone.utc):
                    alias = {**drive_data, 'id': doc.id}
                    alias['position'] = drive_data.get('job_role')
                    alias['deadline'] = drive_data.get('last_date_to_apply')
                    elig = drive_data.get('eligibility_criteria') or {}
                    alias['min_cgpa'] = (elig.get('cgpa') if isinstance(elig, dict) else None)
                    alias['departments'] = (elig.get('departments') if isinstance(elig, dict) else [])
                    alias['requirements'] = drive_data.get('skills_required', [])
                    drives.append(alias)
        
        # Sort by last date to apply
        drives.sort(key=lambda x: x.get('last_date_to_apply', ''))
        
    except Exception as e:
        print(f"Error fetching drives: {e}")
        drives = []
    
    return jsonify(drives)

@app.route('/api/drives', methods=['POST'])
@login_required
@require_user_type('placement_officer')
def create_drive():
    user = get_current_user()
    data = request.get_json()
    
    # Schema-compliant document with fallbacks for client field names
    drive_data = {
        'posted_by': user['id'],
        'company_name': data.get('company_name'),
        'job_role': data.get('position') or data.get('job_role'),
        'description': data.get('description'),
        'eligibility_criteria': data.get('eligibility_criteria') or {
            'cgpa': float(data.get('min_cgpa', 0)) if data.get('min_cgpa') is not None else None,
            'departments': data.get('departments', [])
        },
        'skills_required': data.get('requirements', []) or data.get('skills_required', []),
        'last_date_to_apply': data.get('deadline') or data.get('last_date_to_apply'),
        'created_at': datetime.now()
    }
    
    doc_ref = db.collection('placement_drives').add(drive_data)
    drive_data['id'] = doc_ref[1].id
    
    return jsonify(drive_data)

@app.route('/api/drives/<drive_id>/apply', methods=['POST'])
@login_required
@require_user_type('student')
def apply_drive(drive_id):
    user = get_current_user()
    
    # Check if already applied
    existing_app = db.collection('applications').where('student_id', '==', user['id']).where('drive_id', '==', drive_id).limit(1).stream()
    if list(existing_app):
        return jsonify({'error': 'Already applied to this drive'}), 400
    
    # Create application
    application_data = {
        'student_id': user['id'],
        'drive_id': drive_id,
        'status': 'pending',
        'applied_at': datetime.now()
    }
    
    doc_ref = db.collection('applications').add(application_data)
    application_data['id'] = doc_ref[1].id
    
    return jsonify(application_data)

@app.route('/api/drives/<drive_id>', methods=['PUT'])
@login_required
@require_user_type('placement_officer')
def update_drive(drive_id):
    user = get_current_user()
    data = request.get_json()
    
    # Check if drive exists and user owns it
    drive_ref = db.collection('placement_drives').document(drive_id)
    drive_doc = drive_ref.get()
    
    if not drive_doc.exists:
        return jsonify({'error': 'Drive not found'}), 404
    
    drive_data = drive_doc.to_dict()
    if drive_data['posted_by'] != user['id']:
        return jsonify({'error': 'Unauthorized'}), 403
    
    # Update drive
    update_data = {
        'company_name': data.get('company_name'),
        'job_role': data.get('position') or data.get('job_role'),
        'description': data.get('description'),
        'eligibility_criteria': data.get('eligibility_criteria') or {
            'cgpa': float(data.get('min_cgpa', 0)) if data.get('min_cgpa') is not None else None,
            'departments': data.get('departments', [])
        },
        'skills_required': data.get('requirements', []) or data.get('skills_required', []),
        'last_date_to_apply': data.get('deadline') or data.get('last_date_to_apply'),
        'updated_at': datetime.now()
    }
    
    drive_ref.update(update_data)
    return jsonify({'success': True, 'message': 'Drive updated successfully'})

@app.route('/api/drives/<drive_id>', methods=['DELETE'])
@login_required
@require_user_type('placement_officer')
def delete_drive(drive_id):
    user = get_current_user()
    
    # Check if drive exists and user owns it
    drive_ref = db.collection('placement_drives').document(drive_id)
    drive_doc = drive_ref.get()
    
    if not drive_doc.exists:
        return jsonify({'error': 'Drive not found'}), 404
    
    drive_data = drive_doc.to_dict()
    if drive_data['posted_by'] != user['id']:
        return jsonify({'error': 'Unauthorized'}), 403
    
    # Delete drive
    drive_ref.delete()
    return jsonify({'success': True, 'message': 'Drive deleted successfully'})

# ==================== TRAINING MATERIALS API ====================

@app.route('/api/training', methods=['POST'])
@login_required
@require_user_type('placement_officer')
def create_training():
    user = get_current_user()
    data = request.get_json()
    
    training_data = {
        'uploaded_by': user['id'],
        'title': data.get('title'),
        'upload_date': datetime.now(),
        'resource_type': data.get('type', 'PDF'),
        'resource_url': data.get('link'),
        'tags': data.get('tags', [])
    }
    
    doc_ref = db.collection('training_resources').add(training_data)
    training_data['id'] = doc_ref[1].id
    
    return jsonify(training_data)

@app.route('/api/training/<training_id>', methods=['PUT'])
@login_required
@require_user_type('placement_officer')
def update_training(training_id):
    user = get_current_user()
    data = request.get_json()
    
    # Check if training material exists and user owns it
    training_ref = db.collection('training_resources').document(training_id)
    training_doc = training_ref.get()
    
    if not training_doc.exists:
        return jsonify({'error': 'Training material not found'}), 404
    
    training_data = training_doc.to_dict()
    if training_data['uploaded_by'] != user['id']:
        return jsonify({'error': 'Unauthorized'}), 403
    
    # Update training material
    update_data = {
        'title': data.get('title'),
        # Schema-compliant fields
        'resource_url': data.get('link') or data.get('resource_url'),
        'resource_type': data.get('type', 'PDF'),
        'tags': data.get('tags', []),
        'updated_at': datetime.now()
    }
    
    training_ref.update(update_data)
    return jsonify({'success': True, 'message': 'Training material updated successfully'})

@app.route('/api/training/<training_id>', methods=['DELETE'])
@login_required
@require_user_type('placement_officer')
def delete_training(training_id):
    user = get_current_user()
    
    # Check if training material exists and user owns it
    training_ref = db.collection('training_resources').document(training_id)
    training_doc = training_ref.get()
    
    if not training_doc.exists:
        return jsonify({'error': 'Training material not found'}), 404
    
    training_data = training_doc.to_dict()
    if training_data['uploaded_by'] != user['id']:
        return jsonify({'error': 'Unauthorized'}), 403
    
    # Delete training material
    training_ref.delete()
    return jsonify({'success': True, 'message': 'Training material deleted successfully'})

# ==================== MESSAGING API ====================

@app.route('/api/messages/<user_id>', methods=['GET'])
@login_required
def get_messages(user_id):
    current_user = get_current_user()
    messages = []
    
    try:
        # Get messages between current user and target user
        messages_ref = db.collection('messages').stream()
        
        for doc in messages_ref:
            msg_data = doc.to_dict()
            # Check if message is between current user and target user
            if ((msg_data['sender_id'] == current_user['id'] and msg_data['receiver_id'] == user_id) or
                (msg_data['sender_id'] == user_id and msg_data['receiver_id'] == current_user['id'])):
                messages.append({**msg_data, 'id': doc.id})
        
        # Normalize timestamp to ISO strings and sort
        norm_messages = []
        for m in messages:
            ts = m.get('timestamp')
            if hasattr(ts, 'isoformat'):
                m['timestamp'] = ts.isoformat()
            elif isinstance(ts, (int, float)):
                m['timestamp'] = datetime.fromtimestamp(ts).isoformat()
            else:
                m['timestamp'] = str(ts or '')
            norm_messages.append(m)

        norm_messages.sort(key=lambda x: x.get('timestamp', ''))
        messages = norm_messages
        
    except Exception as e:
        print(f"Error fetching messages: {e}")
        # Return empty list if index error occurs
        return jsonify([])
    
    return jsonify(messages)

@app.route('/api/messages', methods=['POST'])
@login_required
def send_message():
    current_user = get_current_user()
    data = request.get_json()
    
    message_data = {
        'sender_id': current_user['id'],
        'receiver_id': data.get('receiver_id'),
        'message': data.get('message'),
        'timestamp': datetime.now(),
        'seen': False
    }
    
    doc_ref = db.collection('messages').add(message_data)
    message_data['id'] = doc_ref[1].id
    message_data['timestamp'] = message_data['timestamp'].isoformat()
    
    return jsonify(message_data)

@app.route('/api/messages/<message_id>', methods=['PUT'])
@login_required
def update_message(message_id):
    current_user = get_current_user()
    data = request.get_json()
    
    # Check if message exists and user owns it
    message_ref = db.collection('messages').document(message_id)
    message_doc = message_ref.get()
    
    if not message_doc.exists:
        return jsonify({'error': 'Message not found'}), 404
    
    message_data = message_doc.to_dict()
    if message_data['sender_id'] != current_user['id']:
        return jsonify({'error': 'Unauthorized'}), 403
    
    # Update message
    update_data = {
        'message': data.get('message'),
        'edited_at': datetime.now()
    }
    
    message_ref.update(update_data)
    return jsonify({'success': True, 'message': 'Message updated successfully'})

@app.route('/api/messages/<message_id>', methods=['DELETE'])
@login_required
def delete_message(message_id):
    current_user = get_current_user()
    
    # Check if message exists and user owns it
    message_ref = db.collection('messages').document(message_id)
    message_doc = message_ref.get()
    
    if not message_doc.exists:
        return jsonify({'error': 'Message not found'}), 404
    
    message_data = message_doc.to_dict()
    if message_data['sender_id'] != current_user['id']:
        return jsonify({'error': 'Unauthorized'}), 403
    
    # Delete message
    message_ref.delete()
    return jsonify({'success': True, 'message': 'Message deleted successfully'})

@app.route('/api/messages/<message_id>/read', methods=['PUT'])
@login_required
def mark_message_read(message_id):
    current_user = get_current_user()
    
    # Check if message exists and is for current user
    message_ref = db.collection('messages').document(message_id)
    message_doc = message_ref.get()
    
    if not message_doc.exists:
        return jsonify({'error': 'Message not found'}), 404
    
    message_data = message_doc.to_dict()
    if message_data['receiver_id'] != current_user['id']:
        return jsonify({'error': 'Unauthorized'}), 403
    
    # Mark message as seen (schema field: seen)
    message_ref.update({'seen': True, 'read_at': datetime.now()})
    return jsonify({'success': True, 'message': 'Message marked as read'})

# ==================== LEGACY ROUTES (for backward compatibility) ====================

@app.route('/askai', methods=['POST'])
def chatbot_api_legacy():
    data = request.get_json()
    prompt = data.get('prompt', '')
    return jsonify({'response': ask_chatbot(prompt)})

@app.route('/summarize', methods=['POST'])
def summarize_api_legacy():
    data = request.get_json()
    text = data.get('text', '')
    return jsonify({'summary': summarize_notes(text)})

@app.route('/quiz', methods=['POST'])
def quiz_api_legacy():
    data = request.get_json()
    text = data.get('text', '')
    return jsonify({'quiz': generate_quiz(text)})

if __name__ == '__main__':
    app.run(debug=True)
