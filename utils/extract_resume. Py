import fitz  # PyMuPDF

def extract_text_from_resume(file_path: str) -> str:
    """Extracts clean text from a PDF resume."""
    text = ""
    try:
        with fitz.open(file_path) as pdf:
            for page in pdf:
                text += page.get_text("text")
        return text.strip()
    except Exception as e:
        return f"Error reading resume: {e}"

def create_summary_prompt(text: str) -> str:
    """Creates a clean AI-friendly prompt summary from extracted text."""
    if not text:
        return "No content found in resume."

    text = text.replace("\n", " ").strip()
    summary = (
        "This is a professional resume summary extracted automatically.\n\n"
        f"Key content:\n{text[:1000]}..."  # Trim long resumes
        "\n\nUse this summary to understand the candidate's profile, skills, and experience."
    )
    return summary
