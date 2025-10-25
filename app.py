from flask import Flask, request, jsonify
from flask_cors import CORS
from supabase import create_client, Client
import os
from dotenv import load_dotenv
import requests
import traceback
import logging
import sys
import time

# ----------------------------------------------------------
# Logging setup for Render
# ----------------------------------------------------------
logging.basicConfig(stream=sys.stdout, level=logging.INFO)

# ----------------------------------------------------------
# Load environment variables
# ----------------------------------------------------------
load_dotenv()

app = Flask(__name__)
CORS(app)  # ✅ allow cross-origin requests from frontend

# ----------------------------------------------------------
# Supabase & n8n setup
# ----------------------------------------------------------
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
N8N_WEBHOOK_URL = os.getenv("N8N_WEBHOOK_URL")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ----------------------------------------------------------
# Routes
# ----------------------------------------------------------
@app.route("/submit", methods=["POST"])
def submit_data():
    try:
        # 🧩 Collect form data
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
        # ✅ Upload to Supabase Storage (handles duplicates safely)
        # ----------------------------------------------------------
        file_path = f"{email or name}_{int(time.time())}_{file.filename}"
        logging.info(f"Uploading file to Supabase path: {file_path}")
        file_bytes = file.read()

        try:
            supabase.storage.from_("resumes").upload(file_path, file_bytes)
        except Exception as upload_error:
            logging.warning(f"File may already exist, trying update(): {upload_error}")
            supabase.storage.from_("resumes").update(file_path, file_bytes)

        file_url = f"{SUPABASE_URL}/storage/v1/object/public/resumes/{file_path}"

        # ----------------------------------------------------------
        # ✅ Insert into Users table
        # ----------------------------------------------------------
        user_data = {"name": name, "email": email, "phone": phone}
        user = supabase.table("users").insert(user_data).execute()
        if not user.data:
            raise Exception("User insert failed")
        user_id = user.data[0]["id"]

        # ----------------------------------------------------------
        # ✅ Insert into Preferences table
        # ----------------------------------------------------------
        pref_data = {
            "user_id": user_id,
            "job_title": job_title,
            "skills": skills,
            "location": location,
            "salary_range": salary,
            "experience": experience,
        }
        supabase.table("preferences").insert(pref_data).execute()

        # ----------------------------------------------------------
        # ✅ Insert into Resumes table
        # ----------------------------------------------------------
        resume_data = {"user_id": user_id, "file_url": file_url}
        supabase.table("resumes").insert(resume_data).execute()

        # ----------------------------------------------------------
        # ✅ Trigger n8n webhook (non-blocking)
        # ----------------------------------------------------------
        payload = {
            "user_id": user_id,
            "email": email,
            "job_title": job_title,
            "location": location,
            "skills": skills,
        }
        if N8N_WEBHOOK_URL:
            try:
                requests.post(N8N_WEBHOOK_URL, json=payload, timeout=3)
            except Exception as e:
                logging.warning(f"⚠️ n8n webhook failed: {e}")

        return jsonify({"message": "Data submitted successfully!"}), 200

    except Exception as e:
        logging.error("❌ ERROR in /submit:")
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route("/")
def home():
    return "✅ Job Search Engine Backend Running on Render!"


# ----------------------------------------------------------
# Run Flask for Render hosting
# ----------------------------------------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
