# app/core/config.py
import os
from dotenv import load_dotenv

# Define project root dynamically
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))

# Load environment variables from .env file in the project root
dotenv_path = os.path.join(PROJECT_ROOT, '.env')
if os.path.exists(dotenv_path):
    print(f"Loading environment variables from: {dotenv_path}")
    load_dotenv(dotenv_path=dotenv_path)
else:
    print(f"Warning: .env file not found at {dotenv_path}. Trying system environment.")
    load_dotenv() # Load from system environment if .env not found

# --- Essential Variables ---
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise ValueError("CRITICAL: OPENAI_API_KEY environment variable not set.")

DRIVEMYBOX_API_KEY = os.getenv("DRIVEMYBOX_API_KEY")
if not DRIVEMYBOX_API_KEY:
    raise ValueError("CRITICAL: DRIVEMYBOX_API_KEY environment variable not set.")

DRIVEMYBOX_API_BASE_URL = os.getenv("DRIVEMYBOX_API_BASE_URL", "https://api.placeholder.drivemybox.io/v1")
if "api.placeholder.drivemybox.io" in DRIVEMYBOX_API_BASE_URL:
     print("\n" + "="*20 + " WARNING " + "="*20)
     print("Using placeholder DRIVEMYBOX_API_BASE_URL.")
     print("!!! The Price Quote functionality WILL NOT WORK until you set the correct API base URL in the .env file !!!")
     print("="*50 + "\n")

# --- Path Configuration ---
DATA_DIR = os.getenv("DATA_DIR", os.path.join(PROJECT_ROOT, "data"))
STORAGE_DIR = os.getenv("STORAGE_DIR", os.path.join(PROJECT_ROOT, "storage"))
TEMP_UPLOAD_DIR = os.getenv("TEMP_UPLOAD_DIR", os.path.join(PROJECT_ROOT, "tmp_uploads"))

print(TEMP_UPLOAD_DIR)

# Construct specific paths relative to DATA_DIR
DB_TABLES_DIR = os.path.join(DATA_DIR, os.getenv("DB_TABLES_DIR", "Datenbanktabellen"))
FAQ_DIR = os.path.join(DATA_DIR, os.getenv("FAQ_DIR", "FAQs"))
FAQ_FILE_PATH = os.path.join(FAQ_DIR, os.getenv("FAQ_FILE_PATH", "Solutions.json"))
CSV_FILE_NAME = os.getenv("CSV_FILE_NAME", "_SELECT_b_job_order_ref_b_status_b_load_status_b_transport_categ_202504141317.csv")
CSV_FILE_PATH = os.path.join(DB_TABLES_DIR, CSV_FILE_NAME)
ORDER_DOCS_DIR = os.path.join(DATA_DIR, os.getenv("ORDER_DOCS_DIR", "Auftragsdokumente"))
PRESENTATIONS_DIR = os.path.join(DATA_DIR, os.getenv("PRESENTATIONS_DIR", "Prasentationen"))

# --- LlamaIndex/Model Settings ---
LLM_MODEL_NAME = os.getenv("LLM_MODEL_NAME", "gpt-4o")
EMBED_MODEL_NAME = os.getenv("EMBED_MODEL_NAME", "text-embedding-3-small")

# --- Ensure temp directory exists ---
# Moved this here after TEMP_UPLOAD_DIR is defined
try:
    os.makedirs(TEMP_UPLOAD_DIR, exist_ok=True)
    print(f"Ensured temporary upload directory exists: {TEMP_UPLOAD_DIR}")
except OSError as e:
    print(f"Warning: Could not create temporary upload directory {TEMP_UPLOAD_DIR}: {e}")
# --- End ensure temp directory ---


# --- Print loaded config for verification ---
print("-" * 30)
print("Configuration Loaded:")
print(f"  Project Root: {PROJECT_ROOT}")
print(f"  Data Directory: {DATA_DIR}")
print(f"  Storage Directory: {STORAGE_DIR}")
print(f"  Temp Upload Directory: {TEMP_UPLOAD_DIR}") # Now defined
print(f"  CSV File Path: {CSV_FILE_PATH}")
print(f"  FAQ File Path: {FAQ_FILE_PATH}")
print(f"  Order Docs Dir: {ORDER_DOCS_DIR}")
print(f"  Presentations Dir: {PRESENTATIONS_DIR}")
print(f"  Using LLM: {LLM_MODEL_NAME}")
print(f"  Using Embed Model: {EMBED_MODEL_NAME}")
print(f"  DriveMyBox API Key Loaded: {'Yes' if DRIVEMYBOX_API_KEY else 'NO'}")
print(f"  DriveMyBox API Base URL: {DRIVEMYBOX_API_BASE_URL}")
print("-" * 30)