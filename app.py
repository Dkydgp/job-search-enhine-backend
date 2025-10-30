from flask import Flask, request, jsonify
from flask_cors import CORS
from supabase import create_client, Client
from docx import Document
import fitz, os, uuid, requests
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
# 🧩 Helper functions
# -----------------------------
def extract_text_from_pdf(path):
    text = ""
    with fitz.open(path) as pdf:
        for page in pdf:
            text += page.get_text()
    return text


def extract_text_from_docx(path):
    doc = Document(path)
    return "\n".join(p.text for p in doc.paragraphs)


# -----------------------------
# 🧾 Step 1: Save personal information
# -----------------------------
@app.route("/api/save_personal", methods=["POST"])
def save_personal():
    try:
        data = request.get_json()
        print("🧩 Received personal data:", data)

        result = supabase.table("job_applicants").insert({
            "full_name": data.get("full_name"),
            "email": data.get("email"),
            "phone": data.get("phone"),
            "city": data.get("city"),
            "state": data.get("state"),
            "country": data.get("country")
        }).execute()

        user_id = None
        if result.data and len(result.data) > 0 and "id" in result.data[0]:
            user_id = str(result.data[0]["id"])
        else:
            print("⚠️ Supabase did not return id:", result.data)

        return jsonify({"status": "success", "user_id": user_id}), 200
    except Exception as e:
        print("❌ Error saving personal info:", e)
        return jsonify({"status": "error", "message": str(e)}), 500


# -----------------------------
# 💼 Step 2: Save job preferences
# -----------------------------
@app.route("/api/save_preferences", methods=["POST"])
def save_preferences():
    try:
        data = request.get_json()
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

        if not result.data:
            print("⚠️ No record found for user_id", user_id)
            return jsonify({"status": "error", "message": "User not found"}), 404

        return jsonify({"status": "success"}), 200
    except Exception as e:
        print("❌ Error saving preferences:", e)
        return jsonify({"status": "error", "message": str(e)}), 500


# -----------------------------
# ✅ Step 3: Finalize submission
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

        if not result.data:
            print("⚠️ No record found to finalize for id", user_id)
            return jsonify({"status": "error", "message": "No record found"}), 404

        print(f"✅ Finalized successfully for user_id={user_id}")
        return jsonify({"status": "success", "message": "Application finalized successfully!"}), 200
    except Exception as e:
        print("❌ Error finalizing application:", str(e))
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/")
def home():
    return "✅ Job Khojo AI Backend Running"


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
