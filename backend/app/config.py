import os
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "app", "clone_platform.db")
UPLOAD_DIR = os.path.join(BASE_DIR, "app", "uploads")
VECTOR_DIR = os.path.join(BASE_DIR, "app", "vector_store")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") or os.getenv("OPENAI_API_KEY", "")
GEMINI_BASE_URL = os.getenv(
    "GEMINI_BASE_URL",
    "https://generativelanguage.googleapis.com/v1beta/openai/",
)
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-pro")

JWT_SECRET = os.getenv("JWT_SECRET", "change-this-secret-in-production")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", "10080"))

CHAT_RATE_LIMIT = os.getenv("CHAT_RATE_LIMIT", "20/minute")
UPLOAD_RATE_LIMIT = os.getenv("UPLOAD_RATE_LIMIT", "10/minute")

MAX_UPLOAD_MB = 10  # FR-1.1
ALLOWED_DOC_EXTENSIONS = {".pdf", ".docx"}
ALLOWED_CERT_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png"}

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(VECTOR_DIR, exist_ok=True)
