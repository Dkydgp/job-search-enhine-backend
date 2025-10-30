from flask import Flask, request, jsonify
from flask_cors import CORS
from supabase import create_client, Client
from docx import Document
import fitz, os, uuid, requests, traceback
from dotenv import load_dotenv

# -----------------------------
# ⚙️ Load environment variables
# -----------------------------
load_dotenv()
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

# Initialize Supabase
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Flask setup
app = Flask(__name__)
CORS(app)

# -----------------------------
# 🧾 STEP 1 – Save Personal Info
# -----------------------------
@app.route("/api/save_personal", methods=["POST"])
def save_personal():
    """Insert personal info and safely return user_id"""
    try:
        data = request.get_json(force=True)
        print("🧩 Received personal data:", data)

        # Validation
        required = ["full_name", "email", "phone", "city", "state", "country"]
        missing = [f for f in required if not data.get(f)]
        if missing:
            msg = f"Missing fields: {', '.join(missing)}"
            print("⚠️", msg)
            return jsonify({"status": "error", "message": msg}), 400

        # Insert + return inserted row
        result = supabase.table("job_applicants").insert({
            "full_name": data["full_name"],
            "email": data["email"],
            "phone": data["phone"],
            "city": data["city"],
            "state": data["state"],
            "country": data["country"]
        }).select("*").execute()

        print("🧾 Supabase insert result:", result.data)
        if not result.data or len(result.data) == 0:
            return jsonify({"status": "error", "message": "Insert returned no data"}), 500

        user_id = str(result.data[0].get("id"))
        print(f"✅ Created user_id={user_id}")
        return jsonify({"status": "success", "user_id": user_id}), 200

    except Exception as e:
        print("❌ Exception in save_personal:", str(e))
        print(traceback.format_exc())
        return jsonify({"status": "error", "message": str(e)}), 500


# -----------------------------
# 💼 STEP 2 – Save Preferences
# -----------------------------
@app.route("/api/save_preferences", methods=["POST"])
def save_preferences():
    try:
        data = request.get_json(force=True)
        print("💼 Received preferences:", data)
        user_id = data.get("user_id")
        if not user_id:
            return jsonify({"status": "error", "message": "Missing user_id"}), 400

        result = supabase.table("job_applicants").update({
            "job_title": data.get("job_title"),
            "job_type": data.get("job_type"),
            "experience": data.get("experience"),
            "salary": data.get("salary"),
            "industry": data.get("industry"),
            "relocate": data.get("relocate", "off")
        }).eq("id", user_id).execute()

        print("💾 Supabase update result:", result.data)
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
        print("🟦 Finalize called with:", data)

        if not user_id:
            return jsonify({"status": "error", "message": "Missing user_id"}), 400

        result = supabase.table("job_applicants").update({
            "status": "completed"
        }).eq("id", user_id).execute()

        print("✅ Finalized for user_id:", user_id)
        return jsonify({"status": "success", "message": "Application finalized"}), 200

    except Exception as e:
        print("❌ Error finalizing:", str(e))
        print(traceback.format_exc())
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/")
def home():
    return "✅ Job Khojo AI Backend Running"


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
