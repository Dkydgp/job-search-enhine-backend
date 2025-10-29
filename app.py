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

app = Flask(__name__)
CORS(app)

# -----------------------------
# 🧩 Helper functions
# -----------------------------
def extract_text_from_pdf(path):
    """Extract text from PDF"""
    text = ""
    with fitz.open(path) as pdf:
        for page in pdf:
            text += page.get_text()
    return text


def extract_text_from_docx(path):
    """Extract text from DOCX"""
    doc = Document(path)
    return "\n".join(p.text for p in doc.paragraphs)


def get_embedding(text):
    """Generate embeddings via OpenRouter API"""
    try:
        headers = {
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://jobkhojo.ai",  # optional
            "X-Title": "Job Khojo AI Backend"
        }

        payload = {
            "model": "openai/text-embedding-3-small",  # default embedding model
            "input": text[:6000]
        }

        response = requests.post("https://openrouter.ai/api/v1/embeddings",
                                 headers=headers, json=payload)
        result = response.json()

        if "data" in result and len(result["data"]) > 0:
            return result["data"][0]["embedding"]

        print("❌ Embedding error:", result)
        return None

    except Exception as e:
        print("❌ OpenRouter embedding failed:", e)
        return None


# -----------------------------
# 📥 Upload resume + AI embedding
# -----------------------------
@app.route("/api/upload_resume", methods=["POST"])
def upload_resume():
    """Uploads resume, extracts text, generates embeddings, and stores in Supabase."""
    try:
        user_id = request.form.get("user_id")
        resume = request.files.get("resume")

        if not resume:
            return jsonify({"status": "error", "message": "No file uploaded"}), 400

        # Step 1 — Upload to Supabase Storage
        resume_name = f"{user_id}_{uuid.uuid4().hex}_{resume.filename}"
        file_path = f"uploads/{resume_name}"
        bucket = "resumes"

        supabase.storage.from_(bucket).upload(file_path, resume.read())
        resume_url = supabase.storage.from_(bucket).get_public_url(file_path)

        # Step 2 — Save locally for text extraction
        os.makedirs("temp", exist_ok=True)
        local_path = os.path.join("temp", resume.filename)
        resume.save(local_path)

        # Step 3 — Extract text
        text = ""
        if resume.filename.lower().endswith(".pdf"):
            text = extract_text_from_pdf(local_path)
        elif resume.filename.lower().endswith(".docx"):
            text = extract_text_from_docx(local_path)
        else:
            return jsonify({"status": "error", "message": "Unsupported file type"}), 400

        # Step 4 — Generate embedding
        embedding = get_embedding(text)

        # Step 5 — Save to Supabase
        if embedding:
            supabase.table("resume_vectors").insert({
                "user_id": user_id,
                "content": text[:10000],
                "embedding": embedding
            }).execute()

        # Step 6 — Update resume URL in job_applicants
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
# 🧠 Match resumes with job description (AI)
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

        # 1️⃣ Create embedding using OpenRouter
        headers = {
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": "openai/text-embedding-3-small",
            "input": job_desc
        }
        response = requests.post("https://openrouter.ai/api/v1/embeddings",
                                 headers=headers, json=payload)
        job_embedding = response.json()["data"][0]["embedding"]

        # 2️⃣ Call Supabase match_resumes() SQL function
        matches = supabase.rpc("match_resumes", {
            "query_embedding": job_embedding,
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
    return "✅ Job Khojo AI Backend Running via OpenRouter"


# -----------------------------
# 🚀 Run (Render-compatible)
# -----------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
