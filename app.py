from flask import Flask, request, jsonify
from flask_cors import CORS
from supabase import create_client, Client
import os, traceback
from dotenv import load_dotenv

# -----------------------------
# ⚙️ Load environment variables
# -----------------------------
load_dotenv()
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# -----------------------------
# ⚙️ Setup Flask + Supabase
# -----------------------------
app = Flask(__name__)

# ✅ Allow your frontend domain (Render + localhost for testing)
CORS(app, resources={r"/*": {"origins": [
    "https://job-search-engine-frontend.onrender.com",
    "http://localhost:5500",
    "http://127.0.0.1:5500"
]}})

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# -----------------------------
# 🧾 STEP 1 – Save Personal Info
# -----------------------------
@app.route("/api/save_personal", methods=["POST"])
def save_personal():
    try:
        data = request.get_json(force=True)
        print("🧩 Received personal data:", data)

        result = supabase.table("job_applicants").insert({
            "full_name": data.get("full_name"),
            "email": data.get("email"),
            "phone": data.get("phone"),
            "city": data.get("city"),
            "state": data.get("state"),
            "country": data.get("country")
        }).select("*").execute()

        print("🧾 Supabase insert result:", result.data)
        if not result.data:
            return jsonify({"status": "error", "message": "Insert returned no data"}), 500

        user_id = str(result.data[0]["id"])
        return jsonify({"status": "success", "user_id": user_id}), 200

    except Exception as e:
        print("❌ Error in save_personal:", e)
        print(traceback.format_exc())
        return jsonify({"status": "error", "message": str(e)}), 500


# -----------------------------
# 💼 STEP 2 – Save Preferences
# -----------------------------
@app.route("/api/save_preferences", methods=["POST"])
def save_preferences():
    try:
        data = request.get_json(force=True)
        user_id = data.get("user_id")

        if not user_id:
            return jsonify({"status": "error", "message": "Missing user_id"}), 400

        supabase.table("job_applicants").update({
            "job_title": data.get("job_title"),
            "job_type": data.get("job_type"),
            "experience": data.get("experience"),
            "salary": data.get("salary"),
            "industry": data.get("industry"),
            "relocate": data.get("relocate", "off")
        }).eq("id", user_id).execute()

        print("💾 Preferences saved for user_id:", user_id)
        return jsonify({"status": "success"}), 200

    except Exception as e:
        print("❌ Error saving preferences:", e)
        print(traceback.format_exc())
        return jsonify({"status": "error", "message": str(e)}), 500


# -----------------------------
# ✅ STEP 3 – Finalize
# -----------------------------
@app.route("/api/finalize", methods=["POST"])
def finalize():
    try:
        data = request.get_json(force=True)
        user_id = data.get("user_id")

        if not user_id:
            return jsonify({"status": "error", "message": "Missing user_id"}), 400

        supabase.table("job_applicants").update({
            "status": "completed"
        }).eq("id", user_id).execute()

        print(f"✅ Finalized for user_id={user_id}")
        return jsonify({"status": "success", "message": "Application finalized"}), 200

    except Exception as e:
        print("❌ Error finalizing:", e)
        print(traceback.format_exc())
        return jsonify({"status": "error", "message": str(e)}), 500


# -----------------------------
# 🩵 Health Check
# -----------------------------
@app.route("/")
def home():
    return "✅ Job Search Engine Backend Running on Render"


# -----------------------------
# 🚀 Render Entrypoint
# -----------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
