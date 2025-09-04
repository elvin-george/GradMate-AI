from flask import Flask, render_template, request, jsonify, redirect, url_for, session, flash
from flask_cors import CORS
import firebase_admin
from firebase_admin import credentials, firestore, auth
import uuid
from datetime import datetime, timedelta
import json

# AI modules
from ai_modules.chatbot import ask_chatbot
from ai_modules.summarizer import summarize_notes
from ai_modules.quizgen import generate_quiz

# Flask app setup
app = Flask(__name__)
app.secret_key = 'gradmate_ai_secret_key_2024'  # Change this in production
CORS(app)

# 🔹 Initialize Firestore
cred = credentials.Certificate("firebase-key.json")
firebase_admin.initialize_app(cred)
db = firestore.client()

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
            return {**user_doc.to_dict(), 'id': user_doc.id}
    return None

# Helper function to require login
def login_required(f):
    def decorated_function(*args, **kwargs):
        if not is_logged_in():
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
        data = request.get_json()
        email = data.get('email')
        password = data.get('password')
        user_type = data.get('user_type')
        
        # Simple authentication (in production, use proper password hashing)
        user_ref = db.collection('users').where('email', '==', email).where('user_type', '==', user_type).limit(1).stream()
        user = None
        for doc in user_ref:
            user = {**doc.to_dict(), 'id': doc.id}
            break
        
        if user and user.get('password') == password:  # In production, use proper password verification
            session['user_id'] = user['id']
            session['user_type'] = user['user_type']
            session['user_name'] = user['name']
            return jsonify({'success': True, 'redirect': url_for('dashboard')})
        else:
            return jsonify({'success': False, 'message': 'Invalid credentials'})
    
    return render_template('login.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        data = request.get_json()
        user_type = data.get('user_type')
        
        # Only allow student signup - officers must be created manually
        if user_type != 'student':
            return jsonify({'success': False, 'message': 'Only students can sign up. Placement officers are pre-created.'})
        
        user_data = {
            'name': data.get('name'),
            'email': data.get('email'),
            'phone': data.get('phone'),
            'department': data.get('department'),
            'cgpa': float(data.get('cgpa', 0)),
            'skills': data.get('skills', []),
            'password': data.get('password'),
            'user_type': 'student',
            'resume_url': '',
            'created_at': datetime.now()
        }
        
        # Check if email already exists
        existing_user = db.collection('users').where('email', '==', user_data['email']).limit(1).stream()
        if list(existing_user):
            return jsonify({'success': False, 'message': 'Email already registered'})
        
        # Add user to database
        doc_ref = db.collection('users').add(user_data)
        user_data['id'] = doc_ref[1].id
        
        # Auto-login after signup
        session['user_id'] = user_data['id']
        session['user_type'] = user_data['user_type']
        session['user_name'] = user_data['name']
        
        return jsonify({'success': True, 'redirect': url_for('dashboard')})
    
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
                        upcoming_tasks.append({
                            'id': f"{plan_doc.id}_{task.get('task', '')}",
                            'title': task.get('task', ''),
                            'due_date': task.get('due_date'),
                            'status': task.get('status', 'pending')
                        })
        
        # Sort by due date and limit to 5
        upcoming_tasks.sort(key=lambda x: x.get('due_date', ''))
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
                
                if last_date > datetime.now():
                    upcoming_drives.append({**drive_data, 'id': doc.id})
        
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
                        recent_applications.append(app_data)
        
        # Sort by applied_at and limit to 5
        recent_applications.sort(key=lambda x: x.get('applied_at', ''), reverse=True)
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
    
    # Get all tasks for the user
    tasks_ref = db.collection('tasks').where('user_id', '==', user['id']).order_by('due_date').stream()
    tasks = [{**doc.to_dict(), 'id': doc.id} for doc in tasks_ref]
    
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
    
    # Get all active placement drives
    drives_ref = db.collection('placement_drives').where('active', '==', True).order_by('date').stream()
    drives = [{**doc.to_dict(), 'id': doc.id} for doc in drives_ref]
    
    # Get training materials
    training_ref = db.collection('training_materials').order_by('created_at').stream()
    training_materials = [{**doc.to_dict(), 'id': doc.id} for doc in training_ref]
    
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
    
    # Get all drives posted by this officer
    drives_ref = db.collection('placement_drives').where('posted_by', '==', user['id']).order_by('created_at').stream()
    drives = [{**doc.to_dict(), 'id': doc.id} for doc in drives_ref]
    
    return render_template('officer_drives.html', user=user, drives=drives)

@app.route('/officer/training')
@login_required
@require_user_type('placement_officer')
def officer_training():
    user = get_current_user()
    
    # Get all training materials posted by this officer
    materials_ref = db.collection('training_materials').where('posted_by', '==', user['id']).order_by('created_at').stream()
    materials = [{**doc.to_dict(), 'id': doc.id} for doc in materials_ref]
    
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
    quiz = generate_quiz(text)
    
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
                        'plan_id': plan_doc.id
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
        'plan_id': plan_id
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
                
                if last_date > datetime.now():
                    drives.append({**drive_data, 'id': doc.id})
        
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
    
    drive_data = {
        'posted_by': user['id'],
        'company_name': data.get('company_name'),
        'job_role': data.get('position'),
        'description': data.get('description'),
        'eligibility_criteria': {
            'cgpa': float(data.get('min_cgpa', 0)),
            'departments': data.get('departments', [])
        },
        'skills_required': data.get('requirements', []),
        'last_date_to_apply': data.get('deadline'),
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
        'job_role': data.get('position'),
        'description': data.get('description'),
        'eligibility_criteria': {
            'cgpa': float(data.get('min_cgpa', 0)),
            'departments': data.get('departments', [])
        },
        'skills_required': data.get('requirements', []),
        'last_date_to_apply': data.get('deadline'),
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
        'description': data.get('description'),
        'resource_url': data.get('link'),
        'resource_type': data.get('type', 'PDF'),
        'tags': data.get('tags', []),
        'upload_date': datetime.now()
    }
    
    doc_ref = db.collection('training_materials').add(training_data)
    training_data['id'] = doc_ref[1].id
    
    return jsonify(training_data)

@app.route('/api/training/<training_id>', methods=['PUT'])
@login_required
@require_user_type('placement_officer')
def update_training(training_id):
    user = get_current_user()
    data = request.get_json()
    
    # Check if training material exists and user owns it
    training_ref = db.collection('training_materials').document(training_id)
    training_doc = training_ref.get()
    
    if not training_doc.exists:
        return jsonify({'error': 'Training material not found'}), 404
    
    training_data = training_doc.to_dict()
    if training_data['posted_by'] != user['id']:
        return jsonify({'error': 'Unauthorized'}), 403
    
    # Update training material
    update_data = {
        'title': data.get('title'),
        'description': data.get('description'),
        'link': data.get('link'),
        'type': data.get('type', 'general'),
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
    training_ref = db.collection('training_materials').document(training_id)
    training_doc = training_ref.get()
    
    if not training_doc.exists:
        return jsonify({'error': 'Training material not found'}), 404
    
    training_data = training_doc.to_dict()
    if training_data['posted_by'] != user['id']:
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
        
        # Sort by timestamp
        messages.sort(key=lambda x: x.get('timestamp', ''))
        
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
        'message': data.get('content'),
        'timestamp': datetime.now(),
        'seen': False
    }
    
    doc_ref = db.collection('messages').add(message_data)
    message_data['id'] = doc_ref[1].id
    
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
        'content': data.get('content'),
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
    
    # Mark message as read
    message_ref.update({'read': True, 'read_at': datetime.now()})
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
