import os
import datetime
from supabase import create_client, Client

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
BUCKET_NAME = os.getenv("SUPABASE_BUCKET")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def upload_to_supabase(local_path: str, bucket_folder: str, file_name: str) -> str:
    """Uploads file to Supabase Storage and returns public URL."""
    storage_path = f"{bucket_folder}/{file_name}"
    with open(local_path, "rb") as f:
        supabase.storage.from_(BUCKET_NAME).upload(storage_path, f)
    return f"{SUPABASE_URL}/storage/v1/object/public/{BUCKET_NAME}/{storage_path}"

def insert_to_db(data: dict):
    """Insert user record into job_khojo_submissions table."""
    response = supabase.table("job_khojo_submissions").insert(data).execute()
    return response.data
