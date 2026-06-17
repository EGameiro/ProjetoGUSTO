from dotenv import load_dotenv
import os

load_dotenv()

# MySQL
MYSQL_HOST     = os.getenv("MYSQL_HOST", "localhost")
MYSQL_PORT     = int(os.getenv("MYSQL_PORT", 3306))
MYSQL_DB       = os.getenv("MYSQL_DB", "gusto_agent")
MYSQL_USER     = os.getenv("MYSQL_USER", "gusto")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "")

# Redis
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")

# UAZAPI
UAZAPI_BASE_URL = os.getenv("UAZAPI_BASE_URL", "").rstrip("/")
UAZAPI_TOKEN    = os.getenv("UAZAPI_TOKEN", "")
UAZAPI_INSTANCE = os.getenv("UAZAPI_INSTANCE", "")
WEBHOOK_URL     = os.getenv("WEBHOOK_URL", "")   # URL pública deste servidor

# LLM
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

# Google Sheets
GOOGLE_SHEET_ID         = os.getenv("GOOGLE_SHEET_ID", "")
GOOGLE_CREDENTIALS_FILE = os.getenv("GOOGLE_CREDENTIALS_FILE", "credentials/google_service_account.json")

# App
PORT = int(os.getenv("PORT", 8000))
