import sys, os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))  # Ensure utils can be imported

from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
import datetime
import tempfile
import requests

# Import from utils package
from utils.extract_resume import extract_text_from_resume, create_summary_prompt
from utils.supabase_helper import upload_to_supabase, insert_to_db

# Load environment variables
load_dotenv()

app = Flask(__name__)
CORS(app)

# ✅ Main API Endpoint
@app.route("/api/jobform", methods=["POST"])
def receive_form():
    try:
        # Collect form data
        data = request.form.to_dict()
        file = request.files.get("resume")

        if not file:
            return jsonify({"error": "Resume file missing"}), 400

        # Save uploaded file temporarily
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            file.save(tmp.name)
            resume_path = tmp.name

        # ✅ Step 1: Extract text and generate summary
        resume_text = extract_text_from_resume(resume_path)
        summary_prompt = create_summary_prompt(resume_text)

        # ✅ Step 2: Create safe filenames
        timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
        safe_name = data.get("fullName", "User").replace(" ", "_")
        resume_file_name = f"{timestamp}_{safe_name}_resume.pdf"
        summary_file_name = f"{timestamp}_{safe_name}_summary.txt"

        # ✅ Step 3: Upload resume & summary prompt to Supabase Storage
        resume_url = upload_to_supabase(resume_path, "resumes", resume_file_name)
        summary_path = tempfile.NamedTemporaryFile(delete=False, suffix=".txt").name
        with open(summary_path, "w") as f:
            f.write(summary_prompt)
        summary_url = upload_to_supabase(summary_path, "prompt_summaries", summary_file_name)

        # ✅ Step 4: Prepare data to insert in Supabase table
        job_data = {
            "full_name": data.get("fullName"),
            "email": data.get("email"),
            "phone": data.get("phone"),
            "city": data.get("city"),
            "state": data.get("state"),
            "country": data.get("country"),
            "job_title": data.get("jobTitle"),
            "job_type": data.get("jobType"),
            "experience": data.get("experience"),
            "salary": data.get("salary"),
            "industry": data.get("industry"),
            "shift": data.get("shift"),
            "relocate": data.get("relocate") == "on",
            "skills": data.get("skills"),
            "resume_url": resume_url,
            "resume_text": resume_text,
            "summary_prompt": summary_prompt,
            "created_at": datetime.datetime.utcnow().isoformat()
        }

        # ✅ Step 5: Insert data into Supabase
        record = insert_to_db(job_data)[0]

        # ✅ Optional Step 6: Trigger n8n webhook (commented out for now)
        # requests.post("https://your-n8n-url.onrender.com/webhook/jobkhojo", json=record)

        # ✅ Step 7: Return response
        return jsonify({
            "status": "success",
            "message": "Form data saved successfully!",
            "record_id": record["id"],
            "resume_url": resume_url,
            "summary_url": summary_url
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ✅ Health Check Endpoint
@app.route("/", methods=["GET"])
def home():
    return jsonify({"message": "✅ Job Khojo Smart Backend is running"})


# ✅ Start Flask (works for local + Render)
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
