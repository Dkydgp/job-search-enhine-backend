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
CORS(app)  # enable cross-origin access

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
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
# 📨 Submit Route (Handles Supabase + n8n)
# ---------------------------------------------------------
@app.route("/submit", methods=["POST"])
def submit_data():
    try:
        # -------------------------------------------------
        # 📥 1. Handle both JSON and Form Data
        # -------------------------------------------------
        if request.is_json:
            data = request.get_json()
        else:
            data = request.form.to_dict()

        logger.info(f"📥 Received data: {data}")

        # Extract data fields (with fallbacks)
        name = data.get("name", "Unknown")
        email = data.get("email")
        job_title = data.get("job_title", "")
        location = data.get("location", "")
        skills = data.get("skills", "")
        file_path = data.get("file_path", "N/A")

        # -------------------------------------------------
        # 💾 2. Save to Supabase
        # -------------------------------------------------
        # ✅ Fix: include name in user upsert (avoids NOT NULL violation)
        supabase.table("users").upsert(
            {"email": email, "name": name},
            on_conflict="email"
        ).execute()

        # Insert preferences
        supabase.table("preferences").insert({
            "email": email,
            "job_title": job_title,
            "location": location,
            "skills": skills
        }).execute()

        # Insert resume info
        supabase.table("resumes").insert({
            "email": email,
            "file_path": file_path
        }).execute()

        # -------------------------------------------------
        # 🌐 3. Send to n8n Webhook (jobsearch)
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
        # ✅ 4. Return Success Response
        # -------------------------------------------------
        result = {
            "status": "success",
            "message": "Data sent to n8n webhook (jobsearch) successfully!",
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
