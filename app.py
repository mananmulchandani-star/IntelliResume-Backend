import os
import json
import re
from datetime import datetime
from flask import Flask, request, jsonify
from flask_cors import CORS
from groq import Groq

# --- App Initialization ---
app = Flask(__name__)

# CORS Configuration
CORS(app, 
     origins=[
         "http://localhost:5173", 
         "http://127.0.0.1:5173",
         "https://intelli-resume-rontend.vercel.app",
         "https://intelli-resume-rontend-git-main-manan6.vercel.app"
     ])

# Simple in-memory storage (remove database for now)
users_storage = []
resume_sessions = []

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

# Health endpoints
@app.route("/")
def hello():
    return jsonify({
        "message": "🚀 Resume Generator API is running!",
        "status": "success",
        "timestamp": datetime.now().isoformat()
    })

@app.route("/api/health", methods=['GET'])
def health_check():
    return jsonify({
        "status": "healthy", 
        "message": "API is working correctly",
        "timestamp": datetime.now().isoformat()
    })

# Main resume generation endpoint
@app.route("/api/generate-resume-from-prompt", methods=['POST'])
def generate_resume():
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({"error": "No JSON data received"}), 400
            
        user_prompt = data.get('prompt', '')
        full_name = data.get('fullName', '')
        email = data.get('email', '')
        phone = data.get('phone', '')
        location = data.get('location', '')
        stream = data.get('stream', '')
        specific_field = data.get('field', '')
        experience_level = data.get('experienceLevel', '')
        target_role = data.get('targetRole', '')

        api_key = os.environ.get("GROQ_API_KEY")
        if not api_key:
            # Return fallback if no API key
            return jsonify({
                "success": True,
                "resumeData": create_fallback_resume(data),
                "message": "Used fallback resume (API key not configured)"
            })

        prompt = f"""
Create a professional resume in JSON format using this information:

BASIC INFORMATION:
- Name: {full_name}
- Email: {email} 
- Phone: {phone}
- Location: {location}
- Field: {stream}
- Specialization: {specific_field}
- Experience: {experience_level}
- Target Role: {target_role}

BACKGROUND: "{user_prompt}"

Return ONLY valid JSON with this structure:
{{
  "fullName": "{full_name}",
  "email": "{email}",
  "phone": "{phone}",
  "location": "{location}",
  "jobTitle": "Professional title",
  "summary": "50-80 word professional summary",
  "education": [
    {{
      "degree": "Degree name",
      "school": "School name",
      "year": "Year"
    }}
  ],
  "skills": ["Skill 1", "Skill 2", "Skill 3"],
  "projects": [
    {{
      "title": "Project title",
      "description": "Project description",
      "technologies": ["Tech 1", "Tech 2"]
    }}
  ],
  "languages": [
    {{"language": "English", "proficiency": "Fluent"}},
    {{"language": "Hindi", "proficiency": "Native"}}
  ]
}}
"""

        client = Groq(api_key=api_key)
        chat_completion = client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama-3.1-8b-instant",
            temperature=0.1,
            max_tokens=2000
        )
        
        ai_content = chat_completion.choices[0].message.content.strip()
        resume_data = extract_json_from_text(ai_content)
        
        if not resume_data:
            resume_data = create_fallback_resume(data)
        
        return jsonify({
            "success": True,
            "resumeData": resume_data,
            "message": "Resume generated successfully"
        })
        
    except Exception as e:
        print(f"Error: {str(e)}")
        return jsonify({
            "success": False,
            "resumeData": create_fallback_resume(request.get_json() or {}),
            "error": str(e),
            "message": "Used fallback resume due to error"
        })

def create_fallback_resume(data):
    """Create simple fallback resume"""
    return {
        "fullName": data.get('fullName', 'Your Name'),
        "email": data.get('email', 'your.email@example.com'),
        "phone": data.get('phone', ''),
        "location": data.get('location', ''),
        "jobTitle": "Professional",
        "summary": "Experienced professional with strong skills and dedication to excellence. Committed to continuous learning and professional development in the field.",
        "education": [{
            "degree": "Bachelor's Degree",
            "school": "University",
            "year": "2020-2024"
        }],
        "skills": ["Communication", "Problem Solving", "Teamwork", "Adaptability"],
        "projects": [{
            "title": "Professional Project",
            "description": "Completed significant project demonstrating skills and expertise",
            "technologies": ["Relevant Technologies"]
        }],
        "languages": [
            {"language": "English", "proficiency": "Fluent"},
            {"language": "Hindi", "proficiency": "Native"}
        ]
    }

# Simple endpoints (without database)
@app.route("/api/skill-recommendations", methods=['POST'])
def get_skill_recommendations():
    return jsonify({
        "recommendedSkills": ["Python", "JavaScript", "React", "Node.js", "SQL"],
        "totalAvailable": 50
    })

@app.route("/api/signup", methods=['POST'])
def signup():
    return jsonify({"message": "Signup functionality temporarily disabled"})

@app.route("/api/login", methods=['POST']) 
def login():
    return jsonify({"message": "Login functionality temporarily disabled"})

# Vercel compatibility
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
else:
    # For Vercel serverless
    pass
