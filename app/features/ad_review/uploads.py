from pathlib import Path
from fastapi import HTTPException
from app.core.config import IMAGE_TYPES, MAX_IMAGE_MB

def read_image(image):  # Checks an uploaded image and returns its bytes
    suffix = Path(image.filename or "").suffix.lower()  # File extension, e.g. ".png"
    if suffix not in IMAGE_TYPES:  # Not a supported image
        raise HTTPException(400, f"Unsupported file type. Upload {', '.join(IMAGE_TYPES)}.")  # Refuse it
    data = image.file.read()  # The image itself
    if len(data) > MAX_IMAGE_MB * 1024 * 1024:  # Too big
        raise HTTPException(400, f"The image is larger than {MAX_IMAGE_MB} MB.")  # Refuse it
    return data  # The image
