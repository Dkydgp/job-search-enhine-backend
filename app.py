# ---------------------------------------------------------
# app.py — Flask + Supabase + n8n Webhook (jobsearch)
# Render Deployment Ready
# ---------------------------------------------------------
import os
import logging
import requests
from flask import Flask, request, jsonify, make_response
from supabase import create_client, Client
from flask_cors import CORS

# ---------------------------------------------------------
# 🔧 Flask Setup
# ---------------------------------------------------------
app = Flask(__name__)
CORS(app)  # allow frontend/webapp POSTs

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------
# 🌐 Environment Variables
# ---------------------------------------------------------
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
N8N_WEBHOOK_URL = os.getenv("N8N_WEBHOOK_URL", "https://YOUR-N8N-DOMAIN/webhook/jobsearch")

# Initialize Supabase client
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ---------------------------------------------------------
# 🏠 Home Route
# ---------------------------------------------------------
@app.route("/", methods=["GET"])
def home():
    return jsonify({
        "status": "ok",
        "message": "🚀 Job Search Engine Backend is Running!"
    }), 200


# ---------------------------------------------------------
# 📨 Submit Route
# ---------------------------------------------------------
@app.route("/submit", methods=["POST"])
def submit_data():
    try:
        # -------------------------------------------------
        # 📥 1. Accept JSON or Form data
        # -------------------------------------------------
        if request.is_json:
            data = request.get_json()
        else:
            data = request.form.to_dict()

        logger.info(f"📥 Received data: {data}")

        # Extract safely
        name = data.get("name", "Unknown")
        email = data.get("email")
        job_title = data.get("job_title", "")
        location = data.get("location", "")
        skills = data.get("skills", "")
        file_path = data.get("file_path") or data.get("file_url") or "unknown_file"

        if not email:
            return jsonify({"status": "error", "message": "Email is required"}), 400

        # -------------------------------------------------
        # 💾 2. Insert into Supabase Tables (Safe & Structured)
        # -------------------------------------------------
        # ---- USERS ----
        try:
            supabase.table("users").upsert(
                {"email": email, "name": name},
                on_conflict="email"
            ).execute()
            logger.info("✅ User record inserted/updated.")
        except Exception as user_error:
            logger.warning(f"⚠️ Skipped inserting into users: {user_error}")

        # ---- PREFERENCES ----
        try:
            supabase.table("preferences").insert({
                "email": email,
                "job_title": job_title,
                "location": location,
                "skills": skills
            }).execute()
            logger.info("✅ Preferences record inserted.")
        except Exception as pref_error:
            logger.warning(f"⚠️ Skipped inserting into preferences: {pref_error}")

        # ---- RESUMES ----
        try:
            # Match Supabase schema: file_url must exist
            safe_file_url = file_path if file_path.strip() else "unknown_file"
            supabase.table("resumes").insert({
                "email": email,
                "file_url": safe_file_url
            }).execute()
            logger.info("✅ Resume record inserted.")
        except Exception as resume_error:
            logger.warning(f"⚠️ Skipped inserting into resumes: {resume_error}")

        # -------------------------------------------------
        # 🌐 3. Send Payload to n8n Webhook (jobsearch)
        # -------------------------------------------------
        payload = {
            "user_id": data.get("user_id"),
            "email": email,
            "name": name,
            "job_title": job_title,
            "location": location,
            "skills": skills
        }

        headers = {"Content-Type": "application/json"}

        logger.info(f"📡 Sending payload to n8n webhook ({N8N_WEBHOOK_URL}): {payload}")
        n8n_response = requests.post(N8N_WEBHOOK_URL, json=payload, headers=headers, timeout=10)
        logger.info(f"✅ n8n webhook response: {n8n_response.status_code} | {n8n_response.text}")

        # -------------------------------------------------
        # ✅ 4. Send Response to Frontend
        # -------------------------------------------------
        result = {
            "status": "success",
            "message": "Data processed and sent successfully!",
            "n8n_status": n8n_response.status_code,
            "n8n_response": n8n_response.text
        }

        flask_response = make_response(jsonify(result), 200)
        flask_response.headers["Content-Type"] = "application/json"
        return flask_response

    except Exception as e:
        logger.error(f"❌ ERROR in /submit: {e}")
        error_response = make_response(jsonify({
            "status": "error",
            "message": str(e)
        }), 500)
        error_response.headers["Content-Type"] = "application/json"
        return error_response


# ---------------------------------------------------------
# 🚀 Flask Entry Point (Render Compatible)
# ---------------------------------------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    logger.info(f"🚀 Flask server running on port {port}")
    app.run(host="0.0.0.0", port=port)
