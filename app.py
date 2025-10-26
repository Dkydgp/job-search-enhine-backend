from flask import Flask, request, jsonify, make_response
import requests
import logging
from supabase import create_client, Client
import os

app = Flask(__name__)

# ---------------------------------------------------------
# ✅ Setup
# ---------------------------------------------------------
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

N8N_WEBHOOK_URL = "https://YOUR-N8N-DOMAIN/webhook/job-ferch"  # <-- replace with your actual n8n Production URL

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)

# ---------------------------------------------------------
# ✅ Flask route
# ---------------------------------------------------------
@app.route("/submit", methods=["POST"])
def submit_data():
    try:
        data = request.get_json()
        logger.info(f"📥 Received data: {data}")

        # -----------------------------------------------------
        # 🧩 1. Insert/Upsert into Supabase (avoids duplicates)
        # -----------------------------------------------------
        user_data = {
            "email": data.get("email"),
            "name": data.get("name", "Unknown"),
        }
        supabase.table("users").upsert(user_data, on_conflict="email").execute()

        # Example: insert preferences and resumes
        supabase.table("preferences").insert({
            "email": data.get("email"),
            "job_title": data.get("job_title"),
            "location": data.get("location"),
            "skills": data.get("skills"),
        }).execute()

        supabase.table("resumes").insert({
            "email": data.get("email"),
            "file_path": data.get("file_path", "N/A")
        }).execute()

        # -----------------------------------------------------
        # 🧠 2. Send payload to n8n webhook
        # -----------------------------------------------------
        payload = {
            "user_id": data.get("user_id"),
            "email": data.get("email"),
            "job_title": data.get("job_title"),
            "location": data.get("location"),
            "skills": data.get("skills"),
        }

        headers = {
            "Content-Type": "application/json",   # ✅ ensures proper content-type
            "Authorization": "Bearer YOUR_SECRET_TOKEN"  # optional: use if your webhook requires auth
        }

        logger.info(f"📡 Sending payload to n8n webhook: {payload}")
        response = requests.post(N8N_WEBHOOK_URL, json=payload, headers=headers, timeout=10)
        logger.info(f"✅ n8n webhook response: {response.status_code} | {response.text}")

        # -----------------------------------------------------
        # ✅ 3. Return a proper JSON response to frontend
        # -----------------------------------------------------
        result = {
            "status": "success",
            "n8n_status": response.status_code,
            "message": "Data sent to n8n successfully!"
        }

        flask_response = make_response(jsonify(result), 200)
        flask_response.headers["Content-Type"] = "application/json"   # ✅ explicit response header
        return flask_response

    except Exception as e:
        logger.error(f"❌ ERROR in /submit: {e}")
        error_response = make_response(jsonify({
            "status": "error",
            "message": str(e)
        }), 500)
        error_response.headers["Content-Type"] = "application/json"
        return error_response
