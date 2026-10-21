import os
from pathlib import Path
from dotenv import load_dotenv

# Show exactly where Python is running from
print("CURRENT WORKING DIRECTORY:", os.getcwd())

# Show where config.py is located
print("CONFIG FILE LOCATION:", Path(__file__).resolve())

# Try loading .env explicitly from the project root
ENV_PATH = Path(__file__).resolve().parent.parent / ".env"

print("LOOKING FOR .ENV AT:", ENV_PATH)
print(".ENV EXISTS:", ENV_PATH.exists())

load_dotenv(dotenv_path=ENV_PATH)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash")
ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.getenv(
        "ALLOWED_ORIGINS",
        "http://localhost:3000,http://localhost:5173,https://aarshmalik35-afk.github.io"
    ).split(",")
    if origin.strip()
]
print("GEMINI KEY LOADED:", bool(GEMINI_API_KEY))
print("GEMINI KEY LENGTH:", len(GEMINI_API_KEY))
print("GEMINI MODEL:", GEMINI_MODEL)
print("ALLOWED ORIGINS:", ALLOWED_ORIGINS)
