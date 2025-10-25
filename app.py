from flask import Flask, request, jsonify
from supabase import create_client, Client
import os
from dotenv import load_dotenv
import requests

load_dotenv()

app = Flask(__name__)

# Supabase setup
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# n8n webhook URL
N8N_WEBHOOK_URL = os.getenv("N8N_WEBHOOK_URL")

@app.route('/submit', methods=['POST'])
def submit_data():
    name = request.form.get('name')
    email = request.form.get('email')
    job_title = request.form.get('job_title')
    skills = request.form.get('skills')
    location = request.form.get('location')
    salary = request.form.get('salary')
    experience = request.form.get('experience')
    file = request.files.get('resume')

    if not file:
        return jsonify({"error": "Resume file required"}), 400

    # Upload file to Supabase Storage
    file_path = f"{email}_{file.filename}"
    supabase.storage.from_('resumes').upload(file_path, file)
    file_url = f"{SUPABASE_URL}/storage/v1/object/public/resumes/{file_path}"

    # Insert into Users
    user_data = {"name": name, "email": email}
    user = supabase.table("users").insert(user_data).execute()
    user_id = user.data[0]["id"]

    # Insert Preferences
    pref_data = {
        "user_id": user_id,
        "job_title": job_title,
        "skills": skills,
        "location": location,
        "salary_range": salary,
        "experience": experience
    }
    supabase.table("preferences").insert(pref_data).execute()

    # Insert Resume record
    resume_data = {"user_id": user_id, "file_url": file_url}
    supabase.table("resumes").insert(resume_data).execute()

    # Trigger n8n webhook
    payload = {"user_id": user_id, "email": email, "job_title": job_title}
    requests.post(N8N_WEBHOOK_URL, json=payload)

    return jsonify({"message": "Data submitted successfully!"}), 200


@app.route('/')
def home():
    return "✅ Job Search Engine Backend Running!"


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
