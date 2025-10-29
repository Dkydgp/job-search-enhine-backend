from flask import Flask, request, jsonify
from flask_cors import CORS
from supabase import create_client, Client
from openai import OpenAI
from docx import Document
import fitz, os, uuid
from dotenv import load_dotenv

# -----------------------------
# ⚙️  Load environment variables
# -----------------------------
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
openai_client = OpenAI(api_key=OPENAI_API_KEY)

app = Flask(__name__)
CORS(app)

# -----------------------------
# 🧩 Helper functions
# -----------------------------
def extract_text_from_pdf(path):
    """Extract text from PDF file"""
    text = ""
    with fitz.open(path) as pdf:
        for page in pdf:
            text += page.get_text()
    return text

def extract_text_from_docx(path):
    """Extract text from DOCX file"""
    doc = Document(path)
    return "\n".join(p.text for p in doc.paragraphs)

def get_embedding(text):
    """Generate embeddings using OpenAI"""
    try:
        res = openai_client.embeddings.create(
            model="text-embedding-3-small",
            input=text[:6000]  # limit to avoid token overflow
        )
        return res.data[0].embedding
    except Exception as e:
        print("❌ Embedding failed:", e)
        return None

# -----------------------------
# 📥 Upload resume + AI embedding
# -----------------------------
@app.route("/api/upload_resume", methods=["POST"])
def upload_resume():
    """
    1️⃣ Upload resume to Supabase Storage
    2️⃣ Extract text (PDF/DOCX)
    3️⃣ Generate embeddings via OpenAI
    4️⃣ Save in Supabase (resume_vectors table)
    5️⃣ Update applicant record with resume_url
    """
    try:
        user_id = request.form.get("user_id")
        resume = request.files.get("resume")
        if not resume:
            return jsonify({"status": "error", "message": "No file uploaded"}), 400

        # Step 1 — Upload file to Supabase Storage
        resume_name = f"{user_id}_{uuid.uuid4().hex}_{resume.filename}"
        file_path = f"uploads/{resume_name}"
        bucket = "resumes"

        supabase.storage.from_(bucket).upload(file_path, resume.read())
        resume_url = supabase.storage.from_(bucket).get_public_url(file_path)

        # Step 2 — Save locally for text extraction
        os.makedirs("temp", exist_ok=True)
        local_path = os.path.join("temp", resume.filename)
        resume.save(local_path)

        # Step 3 — Extract text from resume
        text = ""
        if resume.filename.lower().endswith(".pdf"):
            text = extract_text_from_pdf(local_path)
        elif resume.filename.lower().endswith(".docx"):
            text = extract_text_from_docx(local_path)
        else:
            return jsonify({"status": "error", "message": "Unsupported file type"}), 400

        # Step 4 — Generate embedding
        embedding = get_embedding(text)

        # Step 5 — Store embedding in Supabase
        if embedding:
            supabase.table("resume_vectors").insert({
                "user_id": user_id,
                "content": text[:10000],
                "embedding": embedding
            }).execute()

        # Step 6 — Update resume URL in job_applicants table
        supabase.table("job_applicants").update({
            "resume_url": resume_url
        }).eq("id", user_id).execute()

        os.remove(local_path)
        return jsonify({
            "status": "success",
            "resume_url": resume_url,
            "message": "Resume uploaded and embedded successfully!"
        })

    except Exception as e:
        print("❌ Error:", e)
        return jsonify({"status": "error", "message": str(e)})

# -----------------------------
# 🧠 Match resumes with job description
# -----------------------------
@app.route("/api/match_jobs", methods=["POST"])
def match_jobs():
    """
    Input:
      {"job_description": "Looking for data analyst skilled in Python and SQL"}
    Output:
      Top 5 matching resumes from resume_vectors
    """
    try:
        job_desc = request.json.get("job_description")
        if not job_desc:
            return jsonify({"status": "error", "message": "Job description missing"}), 400

        # 1️⃣ Create embedding for the job description
        res = openai_client.embeddings.create(
            model="text-embedding-3-small",
            input=job_desc
        )
        embedding = res.data[0].embedding

        # 2️⃣ Call Supabase match_resumes() SQL function
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
# 🩵 Health check
# -----------------------------
@app.route("/")
def home():
    return "✅ Job Khojo AI Backend Running"

# -----------------------------
# 🚀 Run (Render-compatible)
# -----------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
