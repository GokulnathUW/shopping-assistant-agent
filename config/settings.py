import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")
SERPAPI_API_KEY = os.getenv("SERPAPI_API_KEY")
KEEPA_API_KEY = os.getenv("KEEPA_API_KEY")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

# Model names
LOCAL_MODEL_SMALL = "llama3.2:3b"
LOCAL_MODEL_MEDIUM = "mistral:7b"
GROQ_MODEL = "llama-3.1-70b-versatile"