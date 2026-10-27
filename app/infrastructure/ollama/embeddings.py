"""Runs guideline-search embeddings on a separate, processor-only copy of Ollama.

Why: the search model (nomic-embed-text) and the judge (gpt-oss) don't fit on a 16 GB graphics card
together. When both use the same Ollama, every guideline search makes Ollama unload gpt-oss and load it
again afterwards (about 18 seconds each time, plus re-reading its instructions). A second Ollama that
only uses the processor has its own memory, so searches never push gpt-oss off the graphics card.
The search model is tiny, so it's still fast on the processor (about 0.03 seconds per search), and it
gives exactly the same vectors.

The copy uses the models you already downloaded; nothing extra is installed.
"""

import atexit  # Standard library module for running clean-up code when the program ends
import os  # Standard library module for environment variables
import shutil  # Standard library module for finding programs
import subprocess  # Standard library module for starting other programs
import time  # Standard library module for waiting
from urllib.parse import urlparse  # Standard library module for reading web addresses

import ollama  # Ollama's own client

from app.core.config import EMBEDDING_BASE_URL, OLLAMA_URL  # Settings

CPU_PORT = 11435  # Port of the processor-only copy (the normal Ollama uses 11434)
CPU_URL = f"http://127.0.0.1:{CPU_PORT}"  # Its address
_url = None  # The address embeddings use, decided once
_process = None  # The copy we started (if any)


def _reachable(url):  # Does an Ollama answer at this address?
    try:  # It may not be running
        ollama.Client(host=url, timeout=2).list()  # Lightweight supported client API; no model is loaded
        return True  # It answered
    except Exception:  # No answer
        return False  # Not running


def _start_cpu_copy():  # Starts the processor-only Ollama copy; returns True if it's running
    global _process  # Remember the process so it can be stopped later
    exe = shutil.which("ollama")  # Where Ollama is installed
    if not exe:  # Not installed on this computer (e.g. Ollama runs on another machine)
        return False  # Can't start a copy
    env = {**os.environ, "OLLAMA_HOST": f"127.0.0.1:{CPU_PORT}", "CUDA_VISIBLE_DEVICES": "-1", "HIP_VISIBLE_DEVICES": "-1", "OLLAMA_VULKAN": "0", "OLLAMA_KEEP_ALIVE": "-1"}  # Its own port, no graphics card, keep the model loaded
    _process = subprocess.Popen(  # Start it in the background
        [exe, "serve"], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,  # Hide its output
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),  # No extra window on Windows
    )  # End of start
    atexit.register(_stop_cpu_copy)  # Stop it when the app stops
    for _ in range(40):  # Wait up to ~10 seconds for it to be ready
        if _reachable(CPU_URL):  # Ready
            return True  # Done
        time.sleep(0.25)  # Wait a little
    return False  # It didn't start


def _stop_cpu_copy():  # Stops the copy we started
    if _process and _process.poll() is None:  # Still running
        _process.terminate()  # Stop it


def embedding_url():  # The Ollama address used for search embeddings
    global _url  # Decide once, then remember
    if _url:  # Already decided
        return _url  # Reuse it
    if EMBEDDING_BASE_URL != "auto":  # A fixed address was set in .env
        _url = EMBEDDING_BASE_URL  # Use it
    elif urlparse(OLLAMA_URL).hostname not in ("localhost", "127.0.0.1", "::1"):  # The models run on another computer
        _url = OLLAMA_URL  # Use that computer's Ollama
    elif _reachable(CPU_URL) or _start_cpu_copy():  # A processor-only copy is running (or could be started)
        _url = CPU_URL  # Use it
    else:  # Couldn't start one
        _url = OLLAMA_URL  # Fall back to the normal Ollama (works, just slower: searches reload the judge)
    return _url  # The address
