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

# ✅ Allow frontend domain (Render + localhost for testing)
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

        # Validate required fields
        required = ["full_name", "email", "phone", "city", "state", "country"]
        missing = [f for f in required if not data.get(f)]
        if missing:
            return jsonify({"status": "error", "message": f"Missing fields: {', '.join(missing)}"}), 400

        # Step 1 — Insert record (avoid .select() to prevent selvt bug)
        result = supabase.table("job_applicants").insert({
            "full_name": data["full_name"],
            "email": data["email"],
            "phone": data["phone"],
            "city": data["city"],
            "state": data["state"],
            "country": data["country"]
        }).execute()

        print("🧾 Insert result:", getattr(result, "data", result))

        # Step 2 — Retrieve the new user ID safely (fallback lookup)
        lookup = supabase.table("job_applicants").select("id").eq("email", data["email"]).limit(1).execute()
        print("🔍 Lookup result:", lookup.data)

        if not lookup.data or len(lookup.data) == 0:
            return jsonify({"status": "error", "message": "Insert succeeded but user not found"}), 500

        user_id = str(lookup.data[0]["id"])
        print(f"✅ User created successfully: ID={user_id}")

        return jsonify({"status": "success", "user_id": user_id}), 200

    except Exception as e:
        print("❌ Error in save_personal:", e)
        print(traceback.format_exc())
        return jsonify({"status": "error", "message": str(e)}), 500


# -----------------------------
# 💼 STEP 2 – Save Job Preferences
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

        print(f"💾 Preferences saved for user_id={user_id}")
        return jsonify({"status": "success"}), 200

    except Exception as e:
        print("❌ Error saving preferences:", e)
        print(traceback.format_exc())
        return jsonify({"status": "error", "message": str(e)}), 500


# -----------------------------
# ✅ STEP 3 – Finalize Submission
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

        print(f"✅ Finalized application for user_id={user_id}")
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
