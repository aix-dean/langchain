import ollama
from app.core.config import CHAT_CONTEXT_CHARS, CHAT_CONTEXT_LIMIT, COLLECTION, EMBEDDING_MODEL, JUDGE_MODEL, OLLAMA_URL, VISION_MODEL
from app.core.runtime import generation_lock as check_lock
from app.infrastructure.ollama.models import model_capabilities
from app.infrastructure.qdrant.store import passage_count

def status():  # Reports whether Ollama, the models and the guidelines are ready
    info = {  # Defaults (assume nothing works until checked)
        "vision_model": VISION_MODEL, "judge_model": JUDGE_MODEL, "embedding_model": EMBEDDING_MODEL,  # Model names
        "collection": COLLECTION, "ollama": False, "missing_models": [], "qdrant": False, "passages": 0,  # Services
        "judge_tools": False, "device": None, "busy": check_lock.locked(),  # Features and activity
        "context_limit_chars": CHAT_CONTEXT_CHARS, "context_limit_tokens": CHAT_CONTEXT_LIMIT,  # Memory limit per chat (for the usage bar)
    }  # End of defaults
    try:  # Ollama might not be running
        client = ollama.Client(host=OLLAMA_URL)  # Connection to Ollama
        installed = {m.model for m in client.list().models}  # Downloaded models, e.g. "gpt-oss:20b"
        installed |= {name.removesuffix(":latest") for name in installed}  # "nomic-embed-text:latest" also counts as "nomic-embed-text"
        info["ollama"] = True  # Ollama answered
        info["missing_models"] = [m for m in (VISION_MODEL, JUDGE_MODEL, EMBEDDING_MODEL) if m not in installed]  # Models still to download
        info["judge_tools"] = "tools" in model_capabilities()  # Can the judge search the guidelines?
        loaded = client.ps().models  # Models currently in memory
        if loaded:  # Something is loaded
            info["device"] = "GPU" if any((m.size_vram or 0) > 0 for m in loaded) else "CPU"  # Memory on the graphics card means GPU
    except Exception:  # Could not reach Ollama
        pass  # Keep the defaults
    try:  # Qdrant might not be running
        info["passages"] = passage_count()  # Number of guideline passages
        info["qdrant"] = True  # Qdrant answered
    except Exception:  # Could not reach Qdrant, or the collection doesn't exist
        pass  # Keep the defaults
    return info  # Send it to the browser
