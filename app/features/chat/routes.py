import json
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from app.core.config import CHAT_CONTEXT_CHARS
from app.api.streaming import stream_events
from app.features.ad_review.uploads import read_image
from app.features.ad_review.service import check_image
from app.features.chat.service import chat_stream

router = APIRouter(tags=["chat"])

@router.post("/api/chat")
def chat(message: str = Form(""), history: str = Form("[]"), image: UploadFile | None = File(None)):  # Text, earlier messages (JSON), optional image
    try:  # The history must be valid JSON
        earlier = json.loads(history)  # [{"role": "user" | "assistant", "content": "..."}]
    except json.JSONDecodeError:  # Broken history
        earlier = []  # Start without it
    used = sum(len(str(m.get("content", ""))) for m in earlier if isinstance(m, dict)) + len(message)  # This chat's memory use, in characters
    if used > CHAT_CONTEXT_CHARS:  # The chat is full: the AI couldn't re-read all of it
        raise HTTPException(409, "This chat has reached its length limit. Start a new chat to continue.")  # The page shows this
    if image is not None and image.filename:  # An image is attached: check it against the ASC guidelines
        data = read_image(image)  # The image
        return stream_events(lambda: check_image(data, note=message))  # The full check; the message is passed on as context
    if not message.strip():  # No image and no text
        raise HTTPException(400, "Type a message or attach an image.")  # Nothing to do
    return stream_events(lambda: chat_stream(message, earlier if isinstance(earlier, list) else []))  # A chat answer
