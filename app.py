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

        # Step 1 — Insert record
        result = supabase.table("job_applicants").insert({
            "full_name": data["full_name"],
            "email": data["email"],
            "phone": data["phone"],
            "city": data["city"],
            "state": data["state"],
            "country": data["country"]
        }).execute()

        print("🧾 Insert result:", getattr(result, "data", result))

        # Step 2 — Retrieve the new user ID safely
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
            "relocate": data.get("relocate", "off"),
            "resume_url": data.get("resume_url")
        }).eq("id", user_id).execute()

        print(f"💾 Preferences saved for user_id={user_id}")
        return jsonify({"status": "success"}), 200

    except Exception as e:
        print("❌ Error saving preferences:", e)
        print(traceback.format_exc())
        return jsonify({"status": "error", "message": str(e)}), 500


# -----------------------------
# 📎 STEP 2.5 – Upload Resume (Fixed Upload)
# -----------------------------
@app.route("/api/upload_resume", methods=["POST"])
def upload_resume():
    try:
        file = request.files.get("file")
        user_id = request.form.get("user_id")

        if not file or not user_id:
            return jsonify({"status": "error", "message": "Missing file or user_id"}), 400

        # ✅ Validate file extension
        allowed_ext = {"pdf", "doc", "docx"}
        filename = file.filename
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        if ext not in allowed_ext:
            return jsonify({"status": "error", "message": "Invalid file type. Only PDF/DOC/DOCX allowed."}), 400

        # ✅ Prepare unique filename and path
        safe_name = f"{user_id}_{filename.replace(' ', '_')}"
        file_path = f"uploads/{safe_name}"

        # ✅ Read file bytes for upload
        file_bytes = file.read()

        # ✅ Upload to Supabase Storage bucket "resumes"
        response = supabase.storage.from_("resumes").upload(
            path=file_path,
            file=file_bytes,
            file_options={"content-type": "application/octet-stream"},
        )

        # Check if upload failed
        if hasattr(response, "error") and response.error is not None:
            print("❌ Upload error:", response.error)
            return jsonify({"status": "error", "message": str(response.error)}), 500

        # ✅ Generate public URL
        resume_url = supabase.storage.from_("resumes").get_public_url(file_path)
        print(f"📎 Resume uploaded successfully for user_id={user_id}: {resume_url}")

        # ✅ Save the resume URL in the database
        supabase.table("job_applicants").update({"resume_url": resume_url}).eq("id", user_id).execute()

        return jsonify({"status": "success", "resume_url": resume_url}), 200

    except Exception as e:
        print("❌ Error uploading resume:", e)
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
