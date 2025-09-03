from .firebase_config import db

# Add a student user
def add_student(uid, name, email, department, cgpa, skills, resume_url):
    db.collection("users").document(uid).set({
        "name": name,
        "email": email,
        "user_type": "student",
        "department": department,
        "cgpa": cgpa,
        "skills": skills,
        "resume_url": resume_url
    }, merge=True)
    return True

# Add a placement officer
def add_officer(uid, name, email):
    db.collection("users").document(uid).set({
        "name": name,
        "email": email,
        "user_type": "placement_officer"
    }, merge=True)
    return True

# Get user by UID
def get_user(uid):
    doc = db.collection("users").document(uid).get()
    return doc.to_dict() if doc.exists else None

# Update student resume
def update_resume(uid, resume_url):
    db.collection("users").document(uid).update({
        "resume_url": resume_url
    })
    return True
