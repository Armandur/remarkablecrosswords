import os
from pathlib import Path

# Miljövariabler
SESSION_SECRET_KEY = os.environ.get("SESSION_SECRET_KEY", "dev-secret-change-me")
ADMIN_INITIAL_PASSWORD = os.environ.get("ADMIN_INITIAL_PASSWORD", "admin")
DATA_DIR_PATH = Path(os.environ.get("DATA_DIR", "./data")).resolve()
DATABASE_PATH = Path(os.environ.get("DATABASE_PATH", str(DATA_DIR_PATH / "app.db"))).resolve()
REMARKABLE_FOLDER = os.environ.get("REMARKABLE_FOLDER", "/Korsord")
NTFY_URL = os.environ.get("NTFY_URL")
REMARKABLE_CLIENT = os.environ.get("REMARKABLE_CLIENT", "rmapi")
ENABLE_SCHEDULER = os.environ.get("ENABLE_SCHEDULER", "true").lower() == "true"

# Path-objekt
DATA_DIR = DATA_DIR_PATH
DB_PATH = DATABASE_PATH
PDF_INCOMING_DIR = DATA_DIR / "pdfs" / "incoming"
PDF_CROSSWORDS_DIR = DATA_DIR / "pdfs" / "crosswords"
PDF_SYNCED_DIR = DATA_DIR / "pdfs" / "synced"
QUEUE_DIR = Path(os.environ.get("QUEUE_DIR", str(DATA_DIR / "queue"))).resolve()
