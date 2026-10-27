import ollama  # Ollama's own client; it can send images to vision models

from app.core.config import IMAGE_SEED, OLLAMA_URL, VISION_MODEL, VISION_NUM_CTX, VISION_MAX_TOKENS, read_prompt

_thinking_models = {}


def vision_options(client):
    if VISION_MODEL not in _thinking_models:
        _thinking_models[VISION_MODEL] = 'thinking' in (client.show(VISION_MODEL).capabilities or [])
    return {'think': False} if _thinking_models[VISION_MODEL] else {}


def describe_image(image_bytes):  # Step 1: asks the vision model to describe the ad; yields the description piece by piece
    client = ollama.Client(host=OLLAMA_URL)  # Connection to Ollama
    stream = client.chat(  # Send the image and instructions
        model=VISION_MODEL,  # minicpm-v:8b by default
        messages=[  # The conversation
            {"role": "system", "content": read_prompt("describe_system.md")},  # Who it is: an English-only image describer (from the n8n node)
            {"role": "user", "content": read_prompt("describe.md"), "images": [image_bytes]},  # The 7-section description instructions, plus the image
        ],  # End of conversation
        stream=True,  # Send the answer back piece by piece
        **vision_options(client),
        options={"num_ctx": VISION_NUM_CTX, 'num_predict': VISION_MAX_TOKENS, 'temperature': 0, 'seed': IMAGE_SEED},
    )  # End of request
    for part in stream:  # Each piece of the answer
        if part.done_reason == 'length':
            raise RuntimeError('Image description reached its output limit. Increase VISION_MAX_TOKENS or upload a clearer crop; no verdict was issued.')
        text = part.message.content  # The new text
        if text:  # Skip empty pieces
            yield text  # Pass it on
