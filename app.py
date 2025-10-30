import os
import traceback
from flask import Flask, request, jsonify
from werkzeug.utils import secure_filename
from datetime import datetime, timezone
from supabase import create_client, Client
from flask_cors import CORS

# ---------- Configuration ----------
UPLOAD_DIR = "/tmp/resumes"
ALLOWED_EXTENSIONS = {"pdf", "docx", "doc"}
MAX_CONTENT_LENGTH = 8 * 1024 * 1024  # 8 MB

# Supabase Configuration (Environment Variables on Render)
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

# ---------- App Initialization ----------
app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = MAX_CONTENT_LENGTH
CORS(app, origins=["https://job-search-engine-frontend.onrender.com"])  # change to your frontend domain

# Ensure upload directory exists
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Initialize Supabase client
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ---------- Helper Functions ----------
def allowed_file(filename: str) -> bool:
    """Check if uploaded file has an allowed extension"""
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

def log_exception(e: Exception):
    """Log and print full exception trace"""
    print("❌ Exception:", str(e))
    traceback.print_exc()

def upload_to_supabase_storage(file_path: str, filename: str) -> str:
    """Upload file to Supabase Storage and return public URL"""
    try:
        with open(file_path, 'rb') as f:
            file_data = f.read()

        bucket_name = "resumes"
        storage_path = f"uploads/{filename}"

        print(f"📤 Uploading {filename} to Supabase storage...")

        supabase.storage.from_(bucket_name).upload(
            storage_path,
            file_data,
            file_options={"content-type": "application/octet-stream"}
        )

        public_url = supabase.storage.from_(bucket_name).get_public_url(storage_path)
        print(f"✅ Uploaded successfully! URL: {public_url}")
        return public_url
    except Exception as e:
        log_exception(e)
        return None

def insert_application(data: dict):
    """Insert a new job application record into Supabase"""
    try:
        result = supabase.table("job_applications").insert(data).execute()
        return result.data[0]["id"] if result.data else None
    except Exception as e:
        log_exception(e)
        raise

# ---------- Routes ----------
@app.route("/")
def home():
    return """
    <h2>✅ Job Search Engine Backend is Running!</h2>
    <p>Available endpoints:</p>
    <ul>
      <li><b>GET /health</b> → Check backend health</li>
      <li><b>POST /api/upload_resume</b> → Submit job application</li>
    </ul>
    """

@app.route("/health")
def health():
    return jsonify({
        "status": "ok",
        "upload_dir": UPLOAD_DIR,
        "supabase_connected": bool(SUPABASE_URL and SUPABASE_KEY)
    }), 200


@app.route("/api/upload_resume", methods=["POST"])
def upload_resume():
    try:
        # 1️⃣ Validate file presence
        if "resume" not in request.files:
            return jsonify({"error": "Missing resume file"}), 400

        file = request.files["resume"]
        if file.filename == "":
            return jsonify({"error": "No file selected"}), 400
        if not allowed_file(file.filename):
            return jsonify({"error": "Invalid file type. Allowed: PDF, DOCX, DOC"}), 400

        # 2️⃣ Collect all form fields
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        phone = request.form.get("phone", "").strip()
        age = request.form.get("age", "").strip()
        qualification = request.form.get("qualification", "").strip()
        experience = request.form.get("experience", "").strip()
        skills = request.form.get("skills", "").strip()
        job_type = request.form.get("job_type", "").strip()
        state = request.form.get("state", "").strip()
        salary = request.form.get("salary", "").strip()
        industry = request.form.get("industry", "").strip()
        relocate = request.form.get("relocate", "false").lower() == "true"

        # 3️⃣ Validate required fields
        if not all([name, email, phone, qualification, experience, skills, job_type, state, salary, industry]):
            return jsonify({"error": "Missing required fields"}), 400

        # 4️⃣ Validate age (optional)
        try:
            age = int(age) if age else None
            if age and (age < 18 or age > 100):
                return jsonify({"error": "Age must be between 18 and 100"}), 400
        except ValueError:
            return jsonify({"error": "Invalid age format"}), 400

        # 5️⃣ Save file temporarily
        orig_filename = secure_filename(file.filename)
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")
        filename = f"{timestamp}_{orig_filename}"
        save_path = os.path.join(UPLOAD_DIR, filename)
        file.save(save_path)

        # 6️⃣ Upload to Supabase Storage
        resume_url = upload_to_supabase_storage(save_path, filename)
        if not resume_url:
            return jsonify({"error": "Failed to upload file to Supabase"}), 500

        # 7️⃣ Insert record into Supabase table
        record = {
            "name": name,
            "email": email,
            "phone": phone,
            "age": age,
            "qualification": qualification,
            "experience": experience,
            "skills": skills,
            "job_type": job_type,
            "state": state,
            "salary": salary,
            "industry": industry,
            "relocate": relocate,
            "resume_filename": filename,
            "resume_url": resume_url,
            "status": "Pending",
            "created_at": datetime.now(timezone.utc).isoformat()
        }

        app_id = insert_application(record)

        # 8️⃣ Cleanup temp file
        try:
            os.remove(save_path)
        except:
            pass

        # 9️⃣ Respond with success
        return jsonify({
            "message": "✅ Application submitted successfully",
            "application_id": app_id,
            "resume_url": resume_url
        }), 200

    except Exception as e:
        log_exception(e)
        return jsonify({"error": "Internal server error", "details": str(e)}), 500


# ---------- Admin Fetch Route ----------
@app.route("/api/applications", methods=["GET"])
def get_applications():
    """Fetch all job applications (for admin use)"""
    try:
        result = supabase.table("job_applications").select("*").order("created_at", desc=True).execute()
        return jsonify({"applications": result.data}), 200
    except Exception as e:
        log_exception(e)
        return jsonify({"error": "Failed to fetch applications"}), 500


# ---------- Run Server ----------
if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
