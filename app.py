import os
import jwt
from datetime import datetime, timedelta, timezone
from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_cors import CORS
import json
import re
import random
import requests  # Using requests instead of Groq package

# --- App Initialization & Configuration ---
app = Flask(__name__)

# ✅ CORS Configuration
CORS(app, 
     origins=[
         "https://intelli-resume-rontend.vercel.app",
         "https://intelli-resume-rontend-git-main-manan6.vercel.app",
         "https://intelli-resume-rontend-7vpjcjvdj-manan6.vercel.app",
         "http://localhost:5173", 
         "http://127.0.0.1:5173"
     ], 
     supports_credentials=True,
     methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
     allow_headers=["Content-Type", "Authorization", "X-Requested-With"])

app.config['SECRET_KEY'] = 'your-super-secret-key-change-this'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
bcrypt = Bcrypt(app)

# Your existing classes remain the same
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)

class SkillVerification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    skill = db.Column(db.String(100), nullable=False)
    level = db.Column(db.String(20), nullable=False)
    attempts = db.Column(db.Integer, default=0)
    last_attempt = db.Column(db.DateTime)
    is_verified = db.Column(db.Boolean, default=False)
    verified_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# ✅ FIXED GROQ CLIENT USING REQUESTS (More reliable)
def call_groq_api(messages, model="llama-3.1-8b-instant", temperature=0.1, max_tokens=2500):
    """Call GROQ API using requests instead of Groq package"""
    api_key = os.environ.get("GROQ_API_KEY")
    
    if not api_key:
        raise Exception("GROQ_API_KEY environment variable is not set")
    
    url = "https://api.groq.com/openai/v1/chat/completions"
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "messages": messages,
        "model": model,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "top_p": 1,
        "stream": False
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"GROQ API Request failed: {e}")
        raise Exception(f"Failed to connect to AI service: {str(e)}")

def extract_json_from_text(text):
    """Extract JSON from AI response text"""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        json_match = re.search(r'\{.*\}', text, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group())
            except json.JSONDecodeError:
                pass
    return None

def detect_content_type(user_input):
    """Detect if input is about education or experience"""
    education_keywords = ['bca', 'b.c.a', 'bachelor', 'college', 'university', 'student', 'graduated', 'degree', 'school', 'education', 'studied', 'course', 'academic']
    experience_keywords = ['worked', 'job', 'company', 'experience', 'years', 'intern', 'role', 'responsibilities', 'employed', 'professional', 'career', 'industry']
    
    input_lower = user_input.lower()
    
    education_score = sum(1 for keyword in education_keywords if keyword in input_lower)
    experience_score = sum(1 for keyword in experience_keywords if keyword in input_lower)
    
    if education_score > experience_score:
        return 'education'
    elif experience_score > education_score:
        return 'experience'
    else:
        return 'mixed'

def generate_professional_title(user_prompt, specific_field, experience_level):
    """Generate appropriate professional title based on user data"""
    prompt_lower = user_prompt.lower()
    
    # Education-based titles
    if any(word in prompt_lower for word in ['bca', 'computer', 'software', 'programming']):
        if experience_level == 'Student':
            return "Computer Science Student"
        elif experience_level == 'Fresher':
            return "Aspiring Software Developer"
        else:
            return "Software Developer"
    
    elif any(word in prompt_lower for word in ['engineering', 'engineer']):
        return "Engineering Student" if experience_level == 'Student' else "Engineer"
    
    elif any(word in prompt_lower for word in ['business', 'management', 'mba']):
        return "Business Student" if experience_level == 'Student' else "Business Professional"
    
    elif any(word in prompt_lower for word in ['design', 'creative', 'art']):
        return "Design Student" if experience_level == 'Student' else "Designer"
    
    # Field-specific titles
    if specific_field:
        if 'computer' in specific_field.lower():
            return "Computer Science Student" if experience_level == 'Student' else "IT Professional"
        elif 'commerce' in specific_field.lower():
            return "Commerce Student" if experience_level == 'Student' else "Commerce Graduate"
        elif 'science' in specific_field.lower():
            return "Science Student" if experience_level == 'Student' else "Science Professional"
    
    # Default based on experience level
    if experience_level == 'Student':
        return "Student / Recent Graduate"
    elif experience_level == 'Fresher':
        return "Entry-Level Professional"
    elif experience_level == 'Experienced':
        return "Experienced Professional"
    else:
        return "Professional"

def validate_summary_length(summary):
    """Ensure summary is at least 50 words"""
    word_count = len(summary.split())
    if word_count < 50:
        expanders = [
            " Strong foundation in technical principles and practical applications.",
            " Proven ability to adapt quickly and learn new technologies efficiently.",
            " Excellent problem-solving skills with attention to detail and quality.",
            " Committed to continuous learning and professional development.",
            " Effective communicator with strong interpersonal skills and team collaboration abilities.",
            " Seeking to leverage academic knowledge in practical, real-world applications."
        ]
        for expander in expanders:
            if word_count < 50:
                summary += expander
                word_count = len(summary.split())
    return summary

# ✅ HEALTH CHECK ENDPOINT
@app.route("/", methods=['GET'])
def hello():
    return jsonify({
        "message": "🚀 Resume Generator API is running!",
        "status": "success",
        "frontend": "https://intelli-resume-rontend.vercel.app",
        "timestamp": datetime.now().isoformat(),
        "groq_configured": bool(os.environ.get("GROQ_API_KEY"))
    })

@app.route("/api/health", methods=['GET'])
def health_check():
    return jsonify({
        "status": "healthy",
        "message": "API is working correctly",
        "timestamp": datetime.now().isoformat(),
        "groq_key_configured": bool(os.environ.get("GROQ_API_KEY"))
    })

# ✅ MAIN RESUME GENERATION ENDPOINT - FIXED GROQ INTEGRATION
@app.route("/api/generate-resume-from-prompt", methods=['POST', 'OPTIONS'])
def generate_resume():
    try:
        if request.method == 'OPTIONS':
            return jsonify({'status': 'preflight'}), 200
            
        data = request.get_json()
        print("📨 RECEIVED DATA FROM FRONTEND:", data)
        
        if not data:
            return jsonify({"error": "No JSON data received"}), 400
            
        user_prompt = data.get('prompt', '')
        full_name = data.get('fullName', '')
        email = data.get('email', '')
        phone = data.get('phone', '')
        location = data.get('location', '')
        stream = data.get('stream', '')
        specific_field = data.get('field', '')
        user_type = data.get('userType', '')
        experience_level = data.get('experienceLevel', '')
        target_role = data.get('targetRole', '')
        skills_input = data.get('skills', '')
        
        print(f"🔍 Using basic info - Name: {full_name}, Email: {email}")

        # ✅ ENHANCED PROMPT FOR PURE AI-GENERATED CONTENT
        enhanced_prompt = f"""
Create a comprehensive professional resume in JSON format using this information:

USER PROVIDED BASIC INFORMATION (USE THESE EXACT VALUES):
- Full Name: {full_name}
- Email: {email}
- Phone: {phone}
- Location: {location}
- Field/Stream: {stream}
- Specific Field: {specific_field}
- User Type: {user_type}
- Experience Level: {experience_level}
- Target Role: {target_role}
- User Provided Skills: {skills_input}

USER BACKGROUND DESCRIPTION: "{user_prompt}"

CRITICAL INSTRUCTIONS:
1. USE the exact basic information provided above - DO NOT change names or contact details
2. Generate an appropriate professional title/jobTitle based on the user's background and field
3. Create a 50-80 word professional summary
4. Extract education details from the user's background description
5. Generate ALL skills based on the user's field, target role, and experience level
6. Create realistic projects based on their field of study
7. Include work experience only if relevant to their background
8. Add default languages: English and Hindi
9. Output ONLY valid JSON

Return ONLY this JSON structure:
{{
  "fullName": "{full_name}",
  "email": "{email}",
  "phone": "{phone}",
  "location": "{location}",
  "jobTitle": "Professional title based on background and field",
  "summary": "50-80 word professional summary",
  "education": [
    {{
      "id": 1,
      "degree": "Extracted degree",
      "school": "Extracted school", 
      "year": "Extracted year",
      "score": "Extracted score or ''"
    }}
  ],
  "skills": ["AI-generated relevant skills for the field"],
  "projects": [
    {{
      "title": "Relevant project title",
      "description": "Project description",
      "technologies": ["relevant technologies"]
    }}
  ],
  "workExperience": [
    {{
      "id": 1,
      "company": "Company name if mentioned",
      "position": "Position title",
      "startDate": "Start date",
      "endDate": "End date",
      "description": "Responsibilities and achievements"
    }}
  ],
  "internships": [
    {{
      "id": 1,
      "company": "Company name",
      "role": "Intern role",
      "duration": "Duration",
      "description": "Learning and contributions"
    }}
  ],
  "extraCurricular": [
    {{
      "activity": "Activity name",
      "role": "Role played",
      "duration": "Duration",
      "achievements": "Key achievements"
    }}
  ],
  "languages": [
    {{"language": "English", "proficiency": "Native/Fluent"}},
    {{"language": "Hindi", "proficiency": "Native/Fluent"}}
  ],
  "certifications": [],
  "achievements": []
}}

Output ONLY JSON, no other text
"""

        print("🤖 Sending request to GROQ API...")
        
        # ✅ FIXED: Using requests instead of Groq package
        groq_response = call_groq_api([
            {"role": "user", "content": enhanced_prompt}
        ])
        
        ai_content = groq_response['choices'][0]['message']['content'].strip()
        print("✅ AI Raw Output Received")
        
        resume_data = extract_json_from_text(ai_content)
        
        if not resume_data:
            print("❌ AI returned invalid JSON, using enhanced fallback...")
            resume_data = create_fallback_resume(full_name, email, phone, location, user_prompt, stream, specific_field, experience_level, target_role)
        else:
            print("✅ AI returned valid JSON")
            # ✅ ENSURE BASIC INFO IS PRESERVED
            resume_data['fullName'] = full_name or resume_data.get('fullName', 'Your Name')
            resume_data['email'] = email or resume_data.get('email', 'your.email@example.com')
            resume_data['phone'] = phone or resume_data.get('phone', '+1 234 567 8900')
            resume_data['location'] = location or resume_data.get('location', 'Your Location')
            
            # Ensure jobTitle exists and is appropriate
            if 'jobTitle' not in resume_data:
                resume_data['jobTitle'] = generate_professional_title(user_prompt, specific_field, experience_level)
            
            # Ensure languages section exists with defaults
            if 'languages' not in resume_data:
                resume_data['languages'] = [
                    {"language": "English", "proficiency": "Fluent"},
                    {"language": "Hindi", "proficiency": "Native"}
                ]
            
            # Validate and enhance summary
            if 'summary' in resume_data:
                resume_data['summary'] = validate_summary_length(resume_data['summary'])
        
        print("📤 Sending enhanced data to frontend")
        return jsonify({
            "success": True,
            "resumeData": resume_data,
            "message": "Resume generated successfully"
        })
        
    except Exception as e:
        print(f"❌ ERROR in resume generation: {str(e)}")
        # Always return a valid resume using fallback
        data = request.get_json() or {}
        resume_data = create_fallback_resume(
            data.get('fullName', ''), 
            data.get('email', ''), 
            data.get('phone', ''), 
            data.get('location', ''), 
            data.get('prompt', ''),
            data.get('stream', ''),
            data.get('field', ''),
            data.get('experienceLevel', ''),
            data.get('targetRole', '')
        )
        return jsonify({
            "success": False,
            "resumeData": resume_data,
            "error": str(e),
            "message": "Used fallback resume due to AI service issue"
        })

def create_fallback_resume(full_name, email, phone, location, user_prompt, stream, specific_field, experience_level, target_role):
    """Create fallback resume with AI-inspired content"""
    
    # Generate field-specific skills based on stream/field
    field_skills = generate_field_specific_skills(stream, specific_field, target_role)
    
    return {
        "fullName": full_name or "Your Name",
        "email": email or "your.email@example.com",
        "phone": phone or "+1 234 567 8900",
        "location": location or "Your Location",
        "jobTitle": target_role or generate_professional_title(user_prompt, specific_field, experience_level),
        "summary": f"Motivated {experience_level.lower() if experience_level else 'professional'} with background in {specific_field or stream or 'relevant field'}. Seeking {target_role or 'opportunities'} to apply skills and contribute to innovative projects. {user_prompt[:100]}..." + " " * 50,
        
        "education": [{
            "id": 1,
            "degree": "Bachelor's Degree in " + (specific_field or stream or "Relevant Field"),
            "school": "University Name",
            "year": "2020-2024",
            "score": "3.8 GPA"
        }],
        
        "skills": field_skills,
        
        "projects": [{
            "title": f"{specific_field or 'Industry'} Project",
            "description": f"Developed solutions in {specific_field or 'relevant field'} demonstrating technical expertise and problem-solving abilities.",
            "technologies": field_skills[:4] if len(field_skills) > 4 else field_skills
        }],
        
        "workExperience": [],
        "internships": [],
        "extraCurricular": [],
        "languages": [
            {"language": "English", "proficiency": "Fluent"},
            {"language": "Hindi", "proficiency": "Native"}
        ],
        "certifications": [],
        "achievements": []
    }

def generate_field_specific_skills(stream, specific_field, target_role):
    """Generate relevant skills based on field and role"""
    skills = []
    
    # Field-based skill generation
    field_lower = (specific_field or stream or '').lower()
    role_lower = (target_role or '').lower()
    
    if any(word in field_lower for word in ['computer', 'software', 'bca', 'engineering', 'technology', 'developer']):
        skills.extend(['Python', 'Java', 'SQL', 'Data Structures', 'Algorithms', 'Web Development'])
        if 'web' in role_lower or 'frontend' in role_lower:
            skills.extend(['HTML/CSS', 'JavaScript', 'React', 'Node.js'])
        elif 'data' in role_lower:
            skills.extend(['Data Analysis', 'Machine Learning', 'Pandas', 'NumPy'])
    
    elif any(word in field_lower for word in ['business', 'management', 'commerce', 'mba']):
        skills.extend(['Business Analysis', 'Strategic Planning', 'Market Research', 'Financial Analysis'])
        if 'market' in role_lower:
            skills.extend(['Digital Marketing', 'SEO', 'Social Media Marketing'])
        elif 'finance' in role_lower:
            skills.extend(['Financial Modeling', 'Budgeting', 'Forecasting'])
    
    elif any(word in field_lower for word in ['design', 'creative', 'art']):
        skills.extend(['UI/UX Design', 'Adobe Creative Suite', 'Figma', 'Typography'])
        if 'graphic' in role_lower:
            skills.extend(['Illustration', 'Brand Identity', 'Print Design'])
        elif 'ux' in role_lower:
            skills.extend(['User Research', 'Wireframing', 'Prototyping'])
    
    # Add some soft skills if we have few technical skills
    if len(skills) < 5:
        skills.extend(['Problem Solving', 'Project Management', 'Communication'])
    
    return skills[:10]

# ✅ KEEP YOUR EXISTING AUTH ENDPOINTS (they work fine)
@app.route("/api/signup", methods=['POST'])
def signup():
    data = request.get_json()
    username = data.get('username')
    email = data.get('email')
    password = data.get('password')
    if not username or not email or not password:
        return jsonify({"message": "Missing username, email, or password"}), 400
    hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
    new_user = User(username=username, email=email, password_hash=hashed_password)
    try:
        db.session.add(new_user)
        db.session.commit()
        return jsonify({"message": "User created successfully!"}), 201
    except:
        return jsonify({"message": "Username or email already exists"}), 400

@app.route("/api/login", methods=['POST'])
def login():
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')
    user = User.query.filter_by(email=email).first()
    if user and bcrypt.check_password_hash(user.password_hash, password):
        token = jwt.encode({'user_id': user.id, 'exp': datetime.utcnow() + timedelta(hours=24)}, app.config['SECRET_KEY'], algorithm="HS256")
        return jsonify({"token": token})
    return jsonify({"message": "Invalid credentials"}), 401

# ✅ VERCEL COMPATIBILITY
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    print("Server starting on http://localhost:5000")
    app.run(debug=True, host='0.0.0.0', port=5000)
else:
    # For Vercel serverless
    with app.app_context():
        db.create_all()
    application = app
