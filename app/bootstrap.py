"""Startup work owned by the application composition layer."""
from langchain_core.messages import HumanMessage, SystemMessage
from app.core.config import CHAT_REASONING
from app.core.runtime import generation_lock
from app.features.chat.service import system_prompt
from app.infrastructure.ollama.embeddings import embedding_url
from app.infrastructure.ollama.models import get_judge


def warm_up():
    try:
        get_judge(effort=CHAT_REASONING).invoke(
            [SystemMessage(system_prompt()), HumanMessage("Reply OK.")],
            options={"num_predict": 1},
        )
    except Exception:
        # Readiness reports missing services; startup must not block the interface.
        pass


def get_ready():
    embedding_url()
    with generation_lock:
        warm_up()
