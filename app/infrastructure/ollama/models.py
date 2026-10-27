import ollama
from langchain_ollama import ChatOllama
from app.core.config import JUDGE_MODEL, JUDGE_NUM_CTX, JUDGE_REASONING, KEEP_ALIVE, OLLAMA_URL

_capabilities = {}

def model_capabilities(model=JUDGE_MODEL):  # Asks Ollama what a model supports, e.g. {"completion", "tools", "thinking"}
    if model not in _capabilities:  # Not checked yet
        try:  # Ollama might not be running, or the model might not be downloaded
            _capabilities[model] = set(ollama.Client(host=OLLAMA_URL).show(model).capabilities or [])  # Ask Ollama
        except Exception:  # Couldn't find out
            return set()  # Assume nothing extra this time, and try again next time
    return _capabilities[model]  # The remembered answer


def thinking_setting(effort):  # How the model should think: an effort level for gpt-oss, on/off for other thinking models
    if "thinking" not in model_capabilities():  # The model can't think
        return None  # Don't ask it to (it would fail)
    if str(effort).strip().lower() in {"off", "false", "none", "0"}:
        return False  # Explicitly disable thinking for models supporting an on/off control.
    if "gpt-oss" in JUDGE_MODEL and effort in ("low", "medium", "high"):  # gpt-oss supports effort levels
        return effort  # e.g. "low": think briefly, answer much sooner
    return True  # Other thinking models: thinking on


def get_judge(temperature=None, effort=JUDGE_REASONING):  # Creates the judge model client (also used for chat answers)
    return ChatOllama(  # Talk to the model through Ollama
        model=JUDGE_MODEL,  # gpt-oss:20b by default
        base_url=OLLAMA_URL,  # Where Ollama is
        num_ctx=JUDGE_NUM_CTX,  # Room for the instructions, the conversation and the search results
        reasoning=thinking_setting(effort),  # How long to think, kept separate from the answer
        temperature=temperature,  # Lower = sticks closer to the rules, less "creative" (None = the model's default, as in n8n)
        keep_alive=KEEP_ALIVE,  # Stay loaded between messages (reloading takes over a minute)
    )  # End of model setup
