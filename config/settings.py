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
LOCAL_MODEL_SMALL = "llama3.1:8b"
LOCAL_MODEL_MEDIUM = "llama3.1:70b"
GROQ_MODEL_SMALL = "llama-3.1-8b-instant"    # Groq — trusted sources
GROQ_MODEL_LARGE = "llama-3.3-70b-versatile" # Groq — synthesis only

# Trusted editorial domains list (Groq → Tavily include_domains)
TRUSTED_SOURCES_DOMAIN_COUNT_MAX = 15

# Tavily search (domain-restricted review discovery)
TAVILY_SEARCH_MAX_RESULTS = 15
