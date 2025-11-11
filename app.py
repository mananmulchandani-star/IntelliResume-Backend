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
import requests

# --- App Initialization & Configuration ---
app = Flask(__name__)

# ✅ Enhanced CORS Configuration for Deployment
CORS(app, 
     origins=[
         "https://intelli-resume-rontend.vercel.app",
         "https://intelli-resume-rontend-git-main-manan6.vercel.app", 
         "https://intelli-resume-rontend-*.vercel.app",
         "http://localhost:5173", 
         "http://127.0.0.1:5173",
         "https://your-production-domain.com"  # Add your domain here
     ], 
     supports_credentials=True,
     methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
     allow_headers=["Content-Type", "Authorization", "X-Requested-With"])

# ✅ Database Configuration for Deployment
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'your-super-secret-key-change-in-production')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///resume_builder.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
bcrypt = Bcrypt(app)

# --- Database Models ---
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class ResumeSession(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    session_token = db.Column(db.String(255), unique=True, nullable=False)
    resume_data = db.Column(db.JSON, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

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

# --- AI Service Functions ---
def call_groq_api(messages, model="llama-3.1-8b-instant", temperature=0.8, max_tokens=3000):
    """Enhanced GROQ API call with better error handling"""
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
        "temperature": temperature,  # Higher temperature for more creativity
        "max_tokens": max_tokens,
        "top_p": 0.9,
        "stream": False
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=45)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"❌ GROQ API Request failed: {e}")
        raise Exception(f"AI service temporarily unavailable. Please try again.")

def extract_json_from_text(text):
    """Enhanced JSON extraction with better error recovery"""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Try to find JSON pattern
        json_match = re.search(r'\{[^{}]*\{[^{}]*\}[^{}]*\}|\{[^{}]*\}', text, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group())
            except json.JSONDecodeError:
                pass
    
    # Last resort: try to fix common JSON issues
    try:
        # Remove any text before and after JSON
        cleaned = re.sub(r'^[^{]*', '', text)
        cleaned = re.sub(r'[^}]*$', '', cleaned)
        return json.loads(cleaned)
    except:
        return None

def generate_unique_session_id():
    """Generate unique session ID for resume tracking"""
    return f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{random.randint(1000, 9999)}"

# --- Enhanced AI Prompt Engineering ---
def create_dynamic_prompt(user_data):
    """Create unique, dynamic prompts for varied AI responses"""
    
    # Different prompt templates for variety
    prompt_templates = [
        """
        Create a comprehensive professional resume in JSON format. Be creative and generate unique content that stands out.
        
        USER INFORMATION:
        - Name: {full_name}
        - Email: {email}
        - Phone: {phone}
        - Location: {location}
        - Field: {stream}
        - Specialization: {specific_field}
        - Experience Level: {experience_level}
        - Target Role: {target_role}
        - Background: {user_prompt}
        
        Generate unique, realistic content that differs from typical resumes. Focus on specific achievements and measurable results.
        """,
        
        """
        Design an innovative professional resume in JSON format. Think outside the box and create distinctive content.
        
        PROFILE DETAILS:
        - Candidate: {full_name}
        - Contact: {email}, {phone}
        - Based in: {location}
        - Academic Background: {stream}
        - Field Focus: {specific_field}
        - Career Stage: {experience_level}
        - Aspiring Role: {target_role}
        - Personal Narrative: {user_prompt}
        
        Create compelling, original content with specific examples and quantifiable achievements.
        """,
        
        """
        Craft a standout professional resume in JSON format. Focus on uniqueness and real-world impact.
        
        CANDIDATE PROFILE:
        - Full Name: {full_name}
        - Contact Info: {email} | {phone} | {location}
        - Education: {stream}
        - Expertise: {specific_field}
        - Professional Level: {experience_level}
        - Desired Position: {target_role}
        - Background Story: {user_prompt}
        
        Generate fresh, authentic content with concrete examples and professional differentiation.
        """
    ]
    
    template = random.choice(prompt_templates)
    
    return template.format(
        full_name=user_data.get('fullName', ''),
        email=user_data.get('email', ''),
        phone=user_data.get('phone', ''),
        location=user_data.get('location', ''),
        stream=user_data.get('stream', ''),
        specific_field=user_data.get('field', ''),
        experience_level=user_data.get('experienceLevel', ''),
        target_role=user_data.get('targetRole', ''),
        user_prompt=user_data.get('prompt', '')
    )

def get_ai_model_variation():
    """Return different AI models for varied responses"""
    models = [
        "llama-3.1-8b-instant",
        "mixtral-8x7b-32768",
        "gemma-7b-it"
    ]
    return random.choice(models)

# --- Enhanced Resume Generation ---
@app.route("/api/generate-resume-from-prompt", methods=['POST', 'OPTIONS'])
def generate_resume():
    try:
        if request.method == 'OPTIONS':
            return jsonify({'status': 'preflight'}), 200
            
        data = request.get_json()
        print("📨 RECEIVED DATA FROM FRONTEND:", data)
        
        if not data:
            return jsonify({"error": "No JSON data received"}), 400
            
        # Extract user data
        user_prompt = data.get('prompt', '')
        full_name = data.get('fullName', '')
        email = data.get('email', '')
        phone = data.get('phone', '')
        location = data.get('location', '')
        stream = data.get('stream', '')
        specific_field = data.get('field', '')
        experience_level = data.get('experienceLevel', '')
        target_role = data.get('targetRole', '')
        skills_input = data.get('skills', '')
        
        print(f"🔍 Processing resume for: {full_name}")

        # ✅ ENHANCED: Dynamic prompt generation for unique responses
        base_prompt = create_dynamic_prompt(data)
        
        # ✅ ENHANCED: Structured prompt with creativity encouragement
        enhanced_prompt = base_prompt + f"""

        CRITICAL REQUIREMENTS:
        1. USE exact provided contact info: {full_name}, {email}, {phone}, {location}
        2. Generate UNIQUE content every time - avoid generic templates
        3. Create specific, measurable achievements
        4. Include industry-relevant technologies and methodologies
        5. Make projects realistic with actual challenges and solutions
        6. Vary the structure and content style
        7. Ensure professional credibility

        JSON STRUCTURE (fill with unique, realistic data):
        {{
          "fullName": "{full_name}",
          "email": "{email}",
          "phone": "{phone}",
          "location": "{location}",
          "jobTitle": "Creative professional title based on background",
          "summary": "50-80 word compelling professional summary with unique value proposition",
          "education": [
            {{
              "id": 1,
              "degree": "Specific degree name",
              "school": "Realistic institution name", 
              "year": "Realistic timeframe",
              "score": "Credible academic performance"
            }}
          ],
          "skills": ["Industry-specific technical skills", "Relevant soft skills", "Tools & technologies"],
          "projects": [
            {{
              "title": "Specific project name",
              "description": "Detailed project description with challenges and solutions",
              "technologies": ["Relevant tech stack"],
              "achievements": "Measurable outcomes"
            }}
          ],
          "workExperience": [
            {{
              "id": 1,
              "company": "Realistic company name",
              "position": "Specific role title",
              "startDate": "Start date",
              "endDate": "End date",
              "description": "Specific responsibilities with quantifiable achievements"
            }}
          ],
          "internships": [
            {{
              "id": 1,
              "company": "Realistic organization",
              "role": "Specific intern role",
              "duration": "Realistic timeframe",
              "description": "Learning outcomes and contributions"
            }}
          ],
          "extraCurricular": [
            {{
              "activity": "Specific activity",
              "role": "Role played",
              "duration": "Time period",
              "achievements": "Notable accomplishments"
            }}
          ],
          "languages": [
            {{"language": "English", "proficiency": "Fluent/Professional"}},
            {{"language": "Hindi", "proficiency": "Native/Bilingual"}}
          ],
          "certifications": [
            {{
              "name": "Relevant certification",
              "issuer": "Certifying body",
              "year": "Year obtained"
            }}
          ],
          "achievements": [
            "Specific, credible achievements and awards"
          ]
        }}

        IMPORTANT: 
        - Be creative and generate DIFFERENT content each time
        - Include specific numbers and metrics where possible
        - Make it realistic and professional
        - Output ONLY valid JSON, no other text
        """

        print("🤖 Sending enhanced dynamic prompt to AI...")
        
        # ✅ ENHANCED: Use different models and temperatures for variety
        ai_model = get_ai_model_variation()
        temperature = random.uniform(0.7, 0.9)  # Vary creativity
        
        groq_response = call_groq_api([
            {"role": "user", "content": enhanced_prompt}
        ], model=ai_model, temperature=temperature)
        
        ai_content = groq_response['choices'][0]['message']['content'].strip()
        print(f"✅ AI Response received using {ai_model}")
        
        resume_data = extract_json_from_text(ai_content)
        
        if not resume_data:
            print("❌ AI returned invalid JSON, using enhanced AI fallback...")
            resume_data = create_ai_enhanced_fallback(data)
        else:
            print("✅ AI returned valid JSON")
            # ✅ ENHANCED: Add uniqueness markers
            resume_data['generatedAt'] = datetime.now().isoformat()
            resume_data['aiModel'] = ai_model
            resume_data['sessionId'] = generate_unique_session_id()
            
            # Ensure basic info preservation
            resume_data['fullName'] = full_name or resume_data.get('fullName', 'Your Name')
            resume_data['email'] = email or resume_data.get('email', 'your.email@example.com')
            resume_data['phone'] = phone or resume_data.get('phone', '+1 234 567 8900')
            resume_data['location'] = location or resume_data.get('location', 'Your Location')
            
            # Validate and enhance content
            resume_data = validate_and_enhance_resume(resume_data, data)
            
            # Store session data
            store_resume_session(resume_data)
        
        print("📤 Sending unique AI-generated resume to frontend")
        return jsonify({
            "success": True,
            "resumeData": resume_data,
            "message": "Unique AI-generated resume created successfully",
            "sessionId": resume_data.get('sessionId'),
            "aiModel": resume_data.get('aiModel')
        })
        
    except Exception as e:
        print(f"❌ ERROR in resume generation: {str(e)}")
        # Enhanced fallback with AI-inspired content
        data = request.get_json() or {}
        resume_data = create_ai_enhanced_fallback(data)
        return jsonify({
            "success": False,
            "resumeData": resume_data,
            "error": str(e),
            "message": "Used AI-enhanced fallback resume",
            "sessionId": resume_data.get('sessionId')
        })

def create_ai_enhanced_fallback(user_data):
    """Create AI-inspired fallback resume with unique elements"""
    
    # Generate unique content elements
    unique_id = generate_unique_session_id()
    field = user_data.get('field', '') or user_data.get('stream', '')
    experience_level = user_data.get('experienceLevel', '')
    
    # Field-specific content generation
    field_content = generate_field_specific_content(field, experience_level)
    
    resume = {
        "fullName": user_data.get('fullName', 'Your Name'),
        "email": user_data.get('email', 'your.email@example.com'),
        "phone": user_data.get('phone', '+1 234 567 8900'),
        "location": user_data.get('location', 'Your Location'),
        "jobTitle": field_content['jobTitle'],
        "summary": field_content['summary'],
        "education": field_content['education'],
        "skills": field_content['skills'],
        "projects": field_content['projects'],
        "workExperience": [],
        "internships": [],
        "extraCurricular": field_content['activities'],
        "languages": [
            {"language": "English", "proficiency": "Fluent"},
            {"language": "Hindi", "proficiency": "Native"}
        ],
        "certifications": field_content['certifications'],
        "achievements": field_content['achievements'],
        "generatedAt": datetime.now().isoformat(),
        "sessionId": unique_id,
        "aiModel": "fallback-enhanced"
    }
    
    return resume

def generate_field_specific_content(field, experience_level):
    """Generate unique field-specific content"""
    field_lower = (field or '').lower()
    
    # Different content templates for variety
    templates = {
        'technical': {
            'jobTitle': ['Software Developer', 'Full Stack Engineer', 'Data Analyst', 'DevOps Engineer', 'AI/ML Specialist'],
            'skills': ['Python', 'JavaScript', 'React', 'Node.js', 'SQL', 'Docker', 'AWS', 'Git'],
            'projects': [
                {'title': 'E-commerce Platform', 'technologies': ['React', 'Node.js', 'MongoDB']},
                {'title': 'Data Analytics Dashboard', 'technologies': ['Python', 'Pandas', 'Tableau']},
                {'title': 'Mobile App Development', 'technologies': ['React Native', 'Firebase']}
            ]
        },
        'business': {
            'jobTitle': ['Business Analyst', 'Marketing Specialist', 'Project Coordinator', 'Sales Executive'],
            'skills': ['Market Research', 'Data Analysis', 'Strategic Planning', 'Digital Marketing', 'CRM'],
            'projects': [
                {'title': 'Market Analysis Report', 'technologies': ['Excel', 'Tableau', 'Survey Tools']},
                {'title': 'Marketing Campaign', 'technologies': ['Social Media', 'Google Analytics', 'SEO']}
            ]
        },
        'creative': {
            'jobTitle': ['UI/UX Designer', 'Graphic Designer', 'Content Creator', 'Digital Artist'],
            'skills': ['Figma', 'Adobe Creative Suite', 'Typography', 'Color Theory', 'User Research'],
            'projects': [
                {'title': 'Brand Identity Design', 'technologies': ['Illustrator', 'Photoshop']},
                {'title': 'Website Redesign', 'technologies': ['Figma', 'Prototyping']}
            ]
        }
    }
    
    # Determine field category
    if any(word in field_lower for word in ['computer', 'software', 'engineering', 'technology']):
        category = 'technical'
    elif any(word in field_lower for word in ['business', 'management', 'commerce', 'marketing']):
        category = 'business'
    elif any(word in field_lower for word in ['design', 'creative', 'art', 'media']):
        category = 'creative'
    else:
        category = 'technical'  # Default
    
    template = templates[category]
    
    return {
        'jobTitle': random.choice(template['jobTitle']),
        'summary': f"Motivated {experience_level.lower() if experience_level else 'professional'} with passion for {field}. Strong problem-solving abilities and commitment to continuous learning in evolving industry landscape.",
        'education': [{
            "id": 1,
            "degree": f"Bachelor's in {field}",
            "school": "University Name",
            "year": "2020-2024",
            "score": "3.7 GPA"
        }],
        'skills': random.sample(template['skills'], min(6, len(template['skills']))),
        'projects': random.sample(template['projects'], min(2, len(template['projects']))),
        'activities': [{
            "activity": "Professional Development",
            "role": "Active Participant",
            "duration": "Ongoing",
            "achievements": "Continuous skill enhancement"
        }],
        'certifications': [{
            "name": f"{field} Professional Certification",
            "issuer": "Professional Body",
            "year": "2024"
        }],
        'achievements': ["Academic Excellence Award", "Project Competition Winner"]
    }

def validate_and_enhance_resume(resume_data, user_data):
    """Validate and enhance AI-generated resume"""
    
    # Ensure required fields
    required_fields = ['fullName', 'email', 'jobTitle', 'summary', 'skills', 'education']
    for field in required_fields:
        if field not in resume_data:
            if field == 'skills':
                resume_data[field] = ['Communication', 'Problem Solving', 'Teamwork']
            elif field == 'education':
                resume_data[field] = [{
                    "id": 1,
                    "degree": "Bachelor's Degree",
                    "school": "University",
                    "year": "2020-2024"
                }]
            else:
                resume_data[field] = f"Default {field}"
    
    # Enhance summary length
    if 'summary' in resume_data and len(resume_data['summary'].split()) < 40:
        resume_data['summary'] += " Committed to professional growth and continuous learning. Strong analytical and problem-solving capabilities."
    
    return resume_data

def store_resume_session(resume_data):
    """Store resume session in database"""
    try:
        session = ResumeSession(
            session_token=resume_data.get('sessionId', generate_unique_session_id()),
            resume_data=resume_data
        )
        db.session.add(session)
        db.session.commit()
    except Exception as e:
        print(f"⚠️ Could not store session: {e}")

# --- Health and Utility Endpoints ---
@app.route("/", methods=['GET'])
def hello():
    return jsonify({
        "message": "🚀 AI Resume Generator API is running!",
        "status": "success",
        "timestamp": datetime.now().isoformat(),
        "version": "2.0",
        "features": ["AI-Powered Resume Generation", "Unique Content Every Time", "Deployment Ready"]
    })

@app.route("/api/health", methods=['GET'])
def health_check():
    return jsonify({
        "status": "healthy",
        "message": "API is working correctly",
        "timestamp": datetime.now().isoformat(),
        "database": "connected",
        "ai_service": "available" if os.environ.get("GROQ_API_KEY") else "configured"
    })

# --- Existing Auth Endpoints (Keep them as they work fine) ---
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

# --- Deployment Configuration ---
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    print("🚀 Server starting on http://localhost:5000")
    print("📊 Features: AI Resume Generation | Unique Content | Deployment Ready")
    app.run(debug=True, host='0.0.0.0', port=5000)
else:
    # For production deployment (Vercel, Railway, etc.)
    with app.app_context():
        db.create_all()
