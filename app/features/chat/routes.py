import json
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from app.core.config import CHAT_CONTEXT_CHARS
from app.api.streaming import stream_events
from app.api.documentation import NDJSONResponse, CHAT_RESPONSES
from app.features.ad_review.uploads import read_image
from app.features.ad_review.service import check_image
from app.features.chat.service import chat_stream

router = APIRouter(tags=["chat"])

@router.post(
    "/api/chat", summary="Chat with Aida or review an attached ad", operation_id="chat_with_aida",
    description="Ask ASC/MACEA questions or attach an image for an ASC check. Supply prior turns in history as a JSON-encoded array of role/content objects. An image message is treated as a reviewer note, not text printed in the ad. Malformed history JSON currently falls back to an empty history.",
    response_class=NDJSONResponse, responses=CHAT_RESPONSES,
)
def chat(message: str = Form("", description="Question or reviewer context. Optional when an image is attached.", examples=["What must an ASC alcohol billboard include?"]), history: str = Form("[]", description="JSON-encoded prior turns; roles are user or assistant, with a content string.", examples=['[{"role":"user","content":"What is MACEA?"},{"role":"assistant","content":"Previous answer"}]']), image: UploadFile | None = File(None, description="Optional JPG/PNG advertisement, up to MAX_IMAGE_MB (default 20 MB).")):  # Text, earlier messages (JSON), optional image
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
