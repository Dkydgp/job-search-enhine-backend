from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
import os, datetime, tempfile, requests

from utils.extract_resume import extract_text_from_resume, create_summary_prompt
from utils.supabase_helper import upload_to_supabase, insert_to_db

load_dotenv()
app = Flask(__name__)
CORS(app)

@app.route("/api/jobform", methods=["POST"])
def receive_form():
    try:
        # Collect form data
        data = request.form.to_dict()
        file = request.files.get("resume")
        if not file:
            return jsonify({"error": "Resume file missing"}), 400

        # Save resume temporarily
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            file.save(tmp.name)
            resume_path = tmp.name

        # Extract text + create summary prompt
        resume_text = extract_text_from_resume(resume_path)
        summary_prompt = create_summary_prompt(resume_text)

        # Generate auto filename with timestamp (acts as unique serial)
        timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
        safe_name = data.get("fullName", "User").replace(" ", "_")
        resume_file_name = f"{timestamp}_{safe_name}_resume.pdf"
        summary_file_name = f"{timestamp}_{safe_name}_summary.txt"

        # Upload resume + summary to Supabase Storage
        resume_url = upload_to_supabase(resume_path, "resumes", resume_file_name)
        summary_path = tempfile.NamedTemporaryFile(delete=False, suffix=".txt").name
        with open(summary_path, "w") as f:
            f.write(summary_prompt)
        summary_url = upload_to_supabase(summary_path, "prompt_summaries", summary_file_name)

        # Prepare record
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

        # Insert record in Supabase
        record = insert_to_db(job_data)[0]

        # Optional: trigger n8n webhook for automation
        # requests.post("https://n8n-yourworkflow.onrender.com/webhook/jobkhojo", json=record)

        return jsonify({
            "status": "success",
            "message": "Data stored successfully!",
            "record_id": record["id"],
            "resume_url": resume_url,
            "summary_url": summary_url
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/", methods=["GET"])
def home():
    return jsonify({"message": "✅ Job Khojo Smart Backend is running"})


if __name__ == "__main__":
    app.run(debug=True)
