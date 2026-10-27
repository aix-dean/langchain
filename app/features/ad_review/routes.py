from fastapi import APIRouter, File, UploadFile
from app.api.streaming import stream_events
from app.features.ad_review.uploads import read_image
from app.features.ad_review.service import check_image

router = APIRouter(tags=["ad-review"])

@router.post("/api/check")
def check(image: UploadFile = File(...)):  # Receives the uploaded image; streams progress and the result back
    data = read_image(image)  # The image
    return stream_events(lambda: check_image(data))  # The full check
