import os  # Standard library module for reading environment variables
from pathlib import Path  # Standard library module for working with file paths

from dotenv import load_dotenv  # Loads settings from the .env file into environment variables

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")  # Read .env (if it exists) so os.getenv can see our settings

MAX_DOCUMENT_MB = int(os.getenv("MAX_DOCUMENT_MB", "20"))

PROMPTS = ROOT / "prompts"  # Folder with the AI instructions and rule summaries

OLLAMA_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")  # Where Ollama runs; this PC by default
VISION_MODEL = os.getenv("VISION_MODEL", "minicpm-v:8b").strip()  # Step 1: the model that looks at the image and describes it
JUDGE_MODEL = os.getenv("JUDGE_MODEL", "gpt-oss:20b").strip()  # Step 2: checks the description against the ASC rules; also answers chat questions
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "nomic-embed-text").strip()  # Turns search text into vectors (must match how the guidelines were stored)
CHAT_HISTORY = int(os.getenv("CHAT_HISTORY", "12"))  # How many earlier chat messages the AI sees when answering
CHAT_REASONING = os.getenv("CHAT_REASONING", "low").strip()  # How long the AI thinks before a chat answer: low (fast), medium or high
JUDGE_REASONING = os.getenv("JUDGE_REASONING", "medium").strip()  # How long it thinks when judging an ad image: low, medium (default) or high
KEEP_ALIVE = os.getenv("KEEP_ALIVE", "30m").strip()  # How long the judge stays loaded after its last use (reloading takes ~80 seconds); "-1" = forever
EMBEDDING_BASE_URL = os.getenv("EMBEDDING_BASE_URL", "auto").strip()  # Where search embeddings run; "auto" = a processor-only Ollama copy the app starts itself
JUDGE_NUM_CTX = int(os.getenv("JUDGE_NUM_CTX", "16384"))  # How much text the judge can read at once. Its instructions alone are ~8,000 tokens; bigger values no longer fit a 16 GB GPU and run much slower
VISION_NUM_CTX = int(os.getenv("VISION_NUM_CTX", "8192"))  # How much text the vision model can read and write at once
CHAT_CONTEXT_LIMIT = int(os.getenv("CHAT_CONTEXT_LIMIT", "0")) or max(2000, JUDGE_NUM_CTX - 11500)  # Memory per chat, in tokens: the earlier messages the AI re-reads each turn. Default = what fits next to its ~11,500 tokens of instructions, searches and answer
CHAT_CONTEXT_CHARS = int(CHAT_CONTEXT_LIMIT * 3.5)  # The same limit in characters (about 3.5 characters per token)
VISION_MAX_TOKENS = int(os.getenv('VISION_MAX_TOKENS', '4096'))
IMAGE_JUDGE_MAX_TOKENS = int(os.getenv('IMAGE_JUDGE_MAX_TOKENS', '6144'))
IMAGE_JUDGE_REASONING = os.getenv('IMAGE_JUDGE_REASONING', 'off').strip()
IMAGE_SEED = int(os.getenv('IMAGE_SEED', '42'))

QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")  # The Qdrant server (the same one n8n uses)
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY") or None  # Only needed if your Qdrant server has a key
COLLECTION = os.getenv("QDRANT_COLLECTION", "asc_guidelines")  # Collection holding the ASC Guidebook passages
TOP_K = int(os.getenv("TOP_K", "3"))  # Passages returned per guideline search (n8n used 3)
MAX_SEARCHES = int(os.getenv("MAX_SEARCHES", "5"))  # Most guideline searches the judge may make per image (its instructions say 2 to 5)

PORT = int(os.getenv("PORT", "8000"))  # Port for the web page: http://127.0.0.1:<PORT>
IMAGE_TYPES = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png"}  # Accepted image files (same as the n8n form)
MAX_IMAGE_MB = int(os.getenv("MAX_IMAGE_MB", "20"))  # Largest image accepted, in megabytes


def read_prompt(name):  # Reads one instruction file from the prompts folder
    return (PROMPTS / name).read_text(encoding="utf-8")  # Its full text

MACEA_COLLECTION = "macea_guidelines"
