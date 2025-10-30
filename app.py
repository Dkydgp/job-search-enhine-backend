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
# 🧩 Helper Functions
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
            "HTTP-Referer": "https://jobkhojo.ai",
            "X-Title": "Job Khojo AI Backend"
        }

        payload = {
            "model": "openai/text-embedding-3-small",
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
# 🧾 Step 1: Save Personal Information
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

        user_id = result.data[0]["id"]
        return jsonify({"status": "success", "user_id": user_id})
    except Exception as e:
        print("❌ Error saving personal info:", e)
        return jsonify({"status": "error", "message": str(e)})


# -----------------------------
# 💼 Step 2: Save Job Preferences
# -----------------------------
@app.route("/api/save_preferences", methods=["POST"])
def save_preferences():
    try:
        data = request.get_json()
        user_id = data.get("user_id")

        supabase.table("job_applicants").update({
            "job_title": data.get("job_title"),
            "job_type": data.get("job_type"),
            "experience": data.get("experience"),
            "salary": data.get("salary"),
            "industry": data.get("industry"),
            "relocate": data.get("relocate", "off")
        }).eq("id", user_id).execute()

        return jsonify({"status": "success"})
    except Exception as e:
        print("❌ Error saving preferences:", e)
        return jsonify({"status": "error", "message": str(e)})


# -----------------------------
# 📤 Step 3: Upload Resume + Embedding
# -----------------------------
@app.route("/api/upload_resume", methods=["POST"])
def upload_resume():
    try:
        user_id = request.form.get("user_id")
        resume = request.files.get("resume")

        if not resume:
            return jsonify({"status": "error", "message": "No file uploaded"}), 400

        resume_name = f"{user_id}_{uuid.uuid4().hex}_{resume.filename}"
        file_path = f"uploads/{resume_name}"
        bucket = "resumes"

        supabase.storage.from_(bucket).upload(file_path, resume.read())
        resume_url = supabase.storage.from_(bucket).get_public_url(file_path)

        os.makedirs("temp", exist_ok=True)
        local_path = os.path.join("temp", resume.filename)
        resume.save(local_path)

        if resume.filename.lower().endswith(".pdf"):
            text = extract_text_from_pdf(local_path)
        elif resume.filename.lower().endswith(".docx"):
            text = extract_text_from_docx(local_path)
        else:
            return jsonify({"status": "error", "message": "Unsupported file type"}), 400

        embedding = get_embedding(text)

        if embedding:
            supabase.table("resume_vectors").insert({
                "user_id": user_id,
                "content": text[:10000],
                "embedding": embedding
            }).execute()

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
# 🧠 Step 4: Match Job Descriptions with Resumes
# -----------------------------
@app.route("/api/match_jobs", methods=["POST"])
def match_jobs():
    try:
        job_desc = request.json.get("job_description")
        if not job_desc:
            return jsonify({"status": "error", "message": "Job description missing"}), 400

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
# ✅ Step 5: Finalize Submission (NEW ROUTE)
# -----------------------------
@app.route("/api/finalize", methods=["POST"])
def finalize():
    """Finalize all steps and confirm completion."""
    try:
        data = request.get_json()
        user_id = data.get("user_id")
        print(f"🟦 Finalize called for user_id={user_id}")

        # Example: mark user as 'completed'
        supabase.table("job_applicants").update({
            "status": "completed"
        }).eq("id", user_id).execute()

        # Optional: Trigger n8n webhook or any automation
        # requests.post("https://your-n8n-url/webhook/finalize", json={"user_id": user_id})

        return jsonify({"status": "success", "message": "Application finalized successfully!"})
    except Exception as e:
        print("❌ Error finalizing application:", e)
        return jsonify({"status": "error", "message": str(e)})


# -----------------------------
# 🩵 Health Check
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
