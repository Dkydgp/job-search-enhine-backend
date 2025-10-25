from flask import Flask, request, jsonify
from flask_cors import CORS
from supabase import create_client, Client
import os
from dotenv import load_dotenv
import requests

# Load environment variables
load_dotenv()

app = Flask(__name__)
CORS(app)  # ✅ Fixes "Network Error" from frontend (allows cross-origin requests)

# Supabase setup
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# n8n webhook URL
N8N_WEBHOOK_URL = os.getenv("N8N_WEBHOOK_URL")

@app.route('/submit', methods=['POST'])
def submit_data():
    try:
        name = request.form.get('name')
        email = request.form.get('email', None)
        phone = request.form.get('phone', None)
        job_title = request.form.get('job_title')
        skills = request.form.get('skills')
        location = request.form.get('location')
        salary = request.form.get('salary')
        experience = request.form.get('experience')
        file = request.files.get('resume')

        if not file:
            return jsonify({"error": "Resume file required"}), 400

        # ✅ Upload file to Supabase Storage
        file_path = f"{email or name}_{file.filename}"
        supabase.storage.from_('resumes').upload(file_path, file)
        file_url = f"{SUPABASE_URL}/storage/v1/object/public/resumes/{file_path}"

        # ✅ Insert user info
        user_data = {"name": name, "email": email, "phone": phone}
        user = supabase.table("users").insert(user_data).execute()
        user_id = user.data[0]["id"]

        # ✅ Insert preferences
        pref_data = {
            "user_id": user_id,
            "job_title": job_title,
            "skills": skills,
            "location": location,
            "salary_range": salary,
            "experience": experience
        }
        supabase.table("preferences").insert(pref_data).execute()

        # ✅ Insert resume record
        resume_data = {"user_id": user_id, "file_url": file_url}
        supabase.table("resumes").insert(resume_data).execute()

        # ✅ Trigger n8n workflow
        payload = {
            "user_id": user_id,
            "email": email,
            "job_title": job_title,
            "location": location,
            "skills": skills
        }
        if N8N_WEBHOOK_URL:
            requests.post(N8N_WEBHOOK_URL, json=payload)

        return jsonify({"message": "Data submitted successfully!"}), 200

    except Exception as e:
        print("Error:", e)
        return jsonify({"error": str(e)}), 500


@app.route('/')
def home():
    return "✅ Job Search Engine Backend Running!"


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
