from flask import Flask, request, jsonify
from flask_cors import CORS
from supabase import create_client, Client
import os
from dotenv import load_dotenv
import requests
import traceback
import logging
import sys

# ----------------------------------------------------------
# Logging setup (forces detailed output to Render console)
# ----------------------------------------------------------
logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)

# ----------------------------------------------------------
# Load environment variables
# ----------------------------------------------------------
load_dotenv()

app = Flask(__name__)
CORS(app)  # allow cross-origin requests from frontend

# ----------------------------------------------------------
# Supabase + n8n setup
# ----------------------------------------------------------
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

N8N_WEBHOOK_URL = os.getenv("N8N_WEBHOOK_URL")


# ----------------------------------------------------------
# Routes
# ----------------------------------------------------------
@app.route("/submit", methods=["POST"])
def submit_data():
    try:
        # Collect form data
        name = request.form.get("name")
        email = request.form.get("email", None)
        phone = request.form.get("phone", None)
        job_title = request.form.get("job_title")
        skills = request.form.get("skills")
        location = request.form.get("location")
        salary = request.form.get("salary")
        experience = request.form.get("experience")
        file = request.files.get("resume")

        if not file:
            return jsonify({"error": "Resume file required"}), 400

        # ----------------------------------------------------------
        # Upload to Supabase Storage
        # ----------------------------------------------------------
        file_path = f"{email or name}_{file.filename}"
        logging.debug(f"Uploading file to Supabase path: {file_path}")
        supabase.storage.from_("resumes").upload(file_path, file)
        file_url = f"{SUPABASE_URL}/storage/v1/object/public/resumes/{file_path}"

        # ----------------------------------------------------------
        # Insert data into Supabase tables
        # ----------------------------------------------------------
        user_data = {"name": name, "email": email, "phone": phone}
        user = supabase.table("users").insert(user_data).execute()
        user_id = user.data[0]["id"]

        pref_data = {
            "user_id": user_id,
            "job_title": job_title,
            "skills": skills,
            "location": location,
            "salary_range": salary,
            "experience": experience,
        }
        supabase.table("preferences").insert(pref_data).execute()

        resume_data = {"user_id": user_id, "file_url": file_url}
        supabase.table("resumes").insert(resume_data).execute()

        # ----------------------------------------------------------
        # Trigger n8n webhook
        # ----------------------------------------------------------
        payload = {
            "user_id": user_id,
            "email": email,
            "job_title": job_title,
            "location": location,
            "skills": skills,
        }
        if N8N_WEBHOOK_URL:
            requests.post(N8N_WEBHOOK_URL, json=payload)

        return jsonify({"message": "Data submitted successfully!"}), 200

    except Exception as e:
        logging.error("❌ ERROR in /submit:")
        traceback.print_exc()  # show full error trace in Render logs
        return jsonify({"error": str(e)}), 500


@app.route("/")
def home():
    return "✅ Job Search Engine Backend Running!"


# ----------------------------------------------------------
# Run Flask with DEBUG mode (shows all errors in Render logs)
# ----------------------------------------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000, debug=True)
