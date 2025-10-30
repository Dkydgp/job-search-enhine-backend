# app.py
import os
import traceback
from flask import Flask, request, jsonify, send_from_directory
from werkzeug.utils import secure_filename
from datetime import datetime

# ---------- Configuration ----------
UPLOAD_DIR = "/tmp/resumes"  # use /tmp on Render to avoid deploy ephemeral problems
ALLOWED_EXTENSIONS = {"pdf", "docx", "doc"}
MAX_CONTENT_LENGTH = 8 * 1024 * 1024  # 8 MB max file size (adjust as needed)

# ---------- App init ----------
app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = MAX_CONTENT_LENGTH

# ensure upload dir exists
os.makedirs(UPLOAD_DIR, exist_ok=True)

# ---------- Helpers ----------
def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

def log_exception(e: Exception):
    # prints to stdout/stderr so Render logs it
    print("❌ Exception:", str(e))
    traceback.print_exc()

# ---------- Routes ----------
@app.route("/")
def index():
    # simple static page if you want to test easily
    return send_from_directory("static", "index.html")

@app.route("/api/upload_resume", methods=["POST"])
def upload_resume():
    try:
        # 1) check the file part exists in request
        if "resume" not in request.files:
            return jsonify({"error": "No file part named 'resume' in the request"}), 400

        file = request.files["resume"]

        # 2) check file selected
        if file.filename == "":
            return jsonify({"error": "No file was selected"}), 400

        # 3) validate extension
        if not allowed_file(file.filename):
            return jsonify({"error": "Invalid file type. Allowed: pdf, docx, doc"}), 400

        # 4) secure filename and add timestamp to avoid collisions
        orig_filename = secure_filename(file.filename)
        timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S%f")
        filename = f"{timestamp}_{orig_filename}"
        save_path = os.path.join(UPLOAD_DIR, filename)

        # 5) save safely
        file.save(save_path)

        # Optional: push to external storage here (commented out below)

        # 6) respond success
        return jsonify({"message": "Uploaded successfully", "filename": filename}), 200

    except Exception as e:
        log_exception(e)
        return jsonify({"error": "Internal server error", "details": str(e)}), 500

# ---------- Health check ----------
@app.route("/health")
def health():
    return jsonify({"status": "ok", "upload_dir": UPLOAD_DIR}), 200

if __name__ == "__main__":
    # For local test
    app.run(debug=True, host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
