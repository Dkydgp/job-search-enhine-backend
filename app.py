# ---------------------------------------------------------
# app.py — Flask + Supabase + n8n (jobsearch) — Render Ready
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
CORS(app)  # allow frontend apps to send POST requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)

# ---------------------------------------------------------
# 🌐 Environment Variables
# ---------------------------------------------------------
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# ✅ Update this to your actual n8n production webhook URL
N8N_WEBHOOK_URL = os.getenv("N8N_WEBHOOK_URL", "https://YOUR-N8N-DOMAIN/webhook/jobsearch")

# Initialize Supabase client
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ---------------------------------------------------------
# 🏠 Root route
# ---------------------------------------------------------
@app.route("/", methods=["GET"])
def home():
    return jsonify({"message": "✅ Job Search Engine Backend is Running!"}), 200

# ---------------------------------------------------------
# 📨 Submit route — handles Supabase + n8n
# ---------------------------------------------------------
@app.route("/submit", methods=["POST"])
def submit_data():
    try:
        # Get JSON from request
        data = request.get_json()
        logger.info(f"📥 Received data: {data}")

        # Extract fields
        email = data.get("email")
        job_title = data.get("job_title")
        location = data.get("location")
        skills = data.get("skills")
        file_path = data.get("file_path", "N/A")

        # -------------------------------------------------
        # 🧠 1. Save to Supabase (upsert user to avoid duplicates)
        # -------------------------------------------------
        supabase.table("users").upsert({"email": email}, on_conflict="email").execute()

        supabase.table("preferences").insert({
            "email": email,
            "job_title": job_title,
            "location": location,
            "skills": skills
        }).execute()

        supabase.table("resumes").insert({
            "email": email,
            "file_path": file_path
        }).execute()

        # -------------------------------------------------
        # 🌐 2. Send payload to n8n webhook (jobsearch)
        # -------------------------------------------------
        payload = {
            "user_id": data.get("user_id"),
            "email": email,
            "job_title": job_title,
            "location": location,
            "skills": skills
        }

        headers = {
            "Content-Type": "application/json"
        }

        logger.info(f"📡 Sending payload to n8n webhook ({N8N_WEBHOOK_URL}): {payload}")
        response = requests.post(N8N_WEBHOOK_URL, json=payload, headers=headers, timeout=10)

        logger.info(f"✅ n8n webhook response: {response.status_code} | {response.text}")

        # -------------------------------------------------
        # ✅ 3. Return response to frontend
        # -------------------------------------------------
        result = {
            "status": "success",
            "supabase_status": "ok",
            "n8n_status": response.status_code,
            "message": "Data sent to n8n webhook (jobsearch) successfully!"
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
# 🚀 Run Flask (Render-compatible)
# ---------------------------------------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    logger.info(f"🚀 Flask server running on port {port}")
    app.run(host="0.0.0.0", port=port)
