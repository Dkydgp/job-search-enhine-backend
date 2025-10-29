from flask import Flask, request, jsonify
from flask_cors import CORS
from supabase import create_client, Client
from openai import OpenAI
from docx import Document
import fitz, os, uuid

# -----------------------------
# 🔧 CONFIGURATION
# -----------------------------
SUPABASE_URL = "https://YOUR-PROJECT-ID.supabase.co"
SUPABASE_KEY = "YOUR-SERVICE-ROLE-KEY"
OPENAI_API_KEY = "YOUR-OPENAI-API-KEY"

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
openai_client = OpenAI(api_key=OPENAI_API_KEY)

app = Flask(__name__)
CORS(app)

# -----------------------------
# 🧩 HELPERS
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

def get_embedding(text):
    try:
        res = openai_client.embeddings.create(
            model="text-embedding-3-small",
            input=text[:6000]
        )
        return res.data[0].embedding
    except Exception as e:
        print("❌ Embedding failed:", e)
        return None

# -----------------------------
# 🧩 STEP 1: Save Personal Info
# -----------------------------
@app.route("/api/save_personal", methods=["POST"])
def save_personal():
    data = request.json
    try:
        result = supabase.table("job_applicants").insert({
            "full_name": data["full_name"],
            "email": data["email"],
            "phone": data["phone"],
            "city": data["city"],
            "state": data["state"],
            "country": data["country"]
        }).execute()
        user_id = result.data[0]["id"]
        return jsonify({"status": "success", "user_id": user_id})
    except Exception as e:
        print("❌ Error saving personal info:", e)
        return jsonify({"status": "error", "message": str(e)})

# -----------------------------
# 🧩 STEP 2: Save Preferences
# -----------------------------
@app.route("/api/save_preferences", methods=["POST"])
def save_preferences():
    data = request.json
    try:
        supabase.table("job_applicants").update({
            "job_title": data["job_title"],
            "job_type": data["job_type"],
            "experience": data["experience"],
            "salary": data["salary"],
            "industry": data["industry"],
            "relocate": data["relocate"]
        }).eq("id", data["user_id"]).execute()
        return jsonify({"status": "success"})
    except Exception as e:
        print("❌ Error saving preferences:", e)
        return jsonify({"status": "error", "message": str(e)})

# -----------------------------
# 🧩 STEP 3: Upload Resume + Create Embedding
# -----------------------------
@app.route("/api/finalize", methods=["POST"])
def finalize():
    try:
        user_id = request.form["user_id"]
        skills = request.form["skills"]
        resume = request.files.get("resume")

        # Upload resume to Supabase Storage
        resume_name = f"{user_id}_{uuid.uuid4().hex}_{resume.filename}"
        file_path = f"uploads/{resume_name}"
        bucket = "resumes"

        supabase.storage.from_(bucket).upload(file_path, resume.read())
        resume_url = supabase.storage.from_(bucket).get_public_url(file_path)

        # Save locally for text extraction
        os.makedirs("temp", exist_ok=True)
        local_path = os.path.join("temp", resume.filename)
        resume.save(local_path)

        # Extract text from resume
        text = ""
        if resume.filename.endswith(".pdf"):
            text = extract_text_from_pdf(local_path)
        elif resume.filename.endswith(".docx"):
            text = extract_text_from_docx(local_path)

        # Generate embeddings
        embedding = get_embedding(text)

        # Update main table
        supabase.table("job_applicants").update({
            "skills": skills,
            "resume_url": resume_url
        }).eq("id", user_id).execute()

        # Save embedding into vector table
        if embedding:
            supabase.table("resume_vectors").insert({
                "user_id": user_id,
                "content": text[:10000],
                "embedding": embedding
            }).execute()

        os.remove(local_path)
        return jsonify({"status": "success", "resume_url": resume_url})

    except Exception as e:
        print("❌ Error in finalize:", e)
        return jsonify({"status": "error", "message": str(e)})

# -----------------------------
# 🧩 STEP 4: Match Jobs (AI Resume Matching)
# -----------------------------
@app.route("/api/match_jobs", methods=["POST"])
def match_jobs():
    """
    Input:
      {
        "job_description": "Looking for data analyst skilled in Python, SQL, Power BI"
      }
    Output:
      Top 5 matching candidates from resume_vectors
    """
    try:
        job_desc = request.json.get("job_description")

        # Create embedding for job description
        res = openai_client.embeddings.create(
            model="text-embedding-3-small",
            input=job_desc
        )
        embedding = res.data[0].embedding

        # Call match_resumes() function in Supabase
        matches = supabase.rpc("match_resumes", {
            "query_embedding": embedding,
            "match_threshold": 0.7,
            "match_count": 5
        }).execute()

        return jsonify({"status": "success", "matches": matches.data})
    except Exception as e:
        print("❌ Error in match_jobs:", e)
        return jsonify({"status": "error", "message": str(e)})

# -----------------------------
# 🩵 TEST ROUTE
# -----------------------------
@app.route("/")
def home():
    return "✅ Job Khojo AI Backend Running"

# -----------------------------
if __name__ == "__main__":
    app.run(debug=True)
