# app.py
import os
import traceback
from flask import Flask, request, jsonify, send_from_directory
from werkzeug.utils import secure_filename
from datetime import datetime
from supabase import create_client, Client
from flask_cors import CORS

# ---------- Configuration ----------
UPLOAD_DIR = "/tmp/resumes"
ALLOWED_EXTENSIONS = {"pdf", "docx", "doc"}
MAX_CONTENT_LENGTH = 8 * 1024 * 1024  # 8 MB

# Supabase Configuration
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

# ---------- App init ----------
app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = MAX_CONTENT_LENGTH
CORS(app, origins=["https://jobkhojo-frontend.onrender.com"])  # <-- Change to your frontend domain

# Ensure upload dir exists
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Initialize Supabase client
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ---------- Helpers ----------
def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

def log_exception(e: Exception):
    print("❌ Exception:", str(e))
    traceback.print_exc()

def upload_to_supabase_storage(file_path: str, filename: str) -> str:
    """Upload file to Supabase Storage and return public URL"""
    try:
        with open(file_path, 'rb') as f:
            file_data = f.read()
        
        bucket_name = "resumes"
        storage_path = f"uploads/{filename}"
        
        supabase.storage.from_(bucket_name).upload(
            storage_path,
            file_data,
            file_options={"content-type": "application/octet-stream"}
        )
        
        public_url = supabase.storage.from_(bucket_name).get_public_url(storage_path)
        return public_url
    except Exception as e:
        log_exception(e)
        return None

def insert_application(data: dict):
    """Insert application data into Supabase database"""
    try:
        result = supabase.table("job_applications").insert({
            "name": data["name"],
            "age": data["age"],
            "qualification": data["qualification"],
            "salary": data["salary"],
            "industry": data["industry"],
            "relocate": data["relocate"],
            "resume_filename": data["resume_filename"],
            "resume_url": data["resume_url"]
        }).execute()
        return result.data[0]["id"] if result.data else None
    except Exception as e:
        log_exception(e)
        raise

# ---------- Routes ----------
@app.route("/")
def index():
    return send_from_directory("static", "index.html")

@app.route("/api/upload_resume", methods=["POST"])
def upload_resume():
    try:
        if "resume" not in request.files:
            return jsonify({"error": "No file part named 'resume' in the request"}), 400

        file = request.files["resume"]
        if file.filename == "":
            return jsonify({"error": "No file was selected"}), 400
        if not allowed_file(file.filename):
            return jsonify({"error": "Invalid file type. Allowed: pdf, docx, doc"}), 400

        # Get form fields
        name = request.form.get("name", "").strip()
        age = request.form.get("age", "")
        qualification = request.form.get("qualification", "").strip()
        salary = request.form.get("salary", "").strip()
        industry = request.form.get("industry", "").strip()
        relocate = request.form.get("relocate", "false").lower() == "true"

        if not all([name, age, qualification, salary, industry]):
            return jsonify({"error": "Missing required form fields"}), 400

        try:
            age = int(age)
            if age < 18 or age > 100:
                return jsonify({"error": "Age must be between 18 and 100"}), 400
        except ValueError:
            return jsonify({"error": "Invalid age value"}), 400

        # Save file locally first
        orig_filename = secure_filename(file.filename)
        timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S%f")
        filename = f"{timestamp}_{orig_filename}"
        save_path = os.path.join(UPLOAD_DIR, filename)
        file.save(save_path)

        # Upload to Supabase Storage
        resume_url = upload_to_supabase_storage(save_path, filename)
        if not resume_url:
            return jsonify({"error": "Failed to upload file to Supabase storage"}), 500

        # Insert into DB
        app_data = {
            "name": name,
            "age": age,
            "qualification": qualification,
            "salary": salary,
            "industry": industry,
            "relocate": relocate,
            "resume_filename": filename,
            "resume_url": resume_url
        }
        app_id = insert_application(app_data)

        # Clean up local temp file
        try: os.remove(save_path)
        except: pass

        return jsonify({
            "message": "Application submitted successfully",
            "application_id": app_id,
            "resume_url": resume_url
        }), 200

    except Exception as e:
        log_exception(e)
        return jsonify({"error": "Internal server error", "details": str(e)}), 500

@app.route("/health")
def health():
    return jsonify({
        "status": "ok",
        "upload_dir": UPLOAD_DIR,
        "supabase_connected": SUPABASE_URL is not None
    }), 200

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
