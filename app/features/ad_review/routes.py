from fastapi import APIRouter, File, UploadFile
from app.api.streaming import stream_events
from app.api.documentation import NDJSONResponse, CHECK_RESPONSES
from app.features.ad_review.uploads import read_image
from app.features.ad_review.service import check_image

router = APIRouter(tags=["ad-review"])

@router.post(
    "/api/check", summary="Pre-screen an advertisement image", operation_id="check_advertisement",
    description="Run image description, ASC guideline retrieval, judgment and verification. This endpoint has no conversation history or reviewer note. Results may require human review; queued requests wait for the current generation to finish.",
    response_class=NDJSONResponse, responses=CHECK_RESPONSES,
)
def check(image: UploadFile = File(..., description="JPG or PNG image; maximum MAX_IMAGE_MB (default 20 MB).")):  # Receives the uploaded image; streams progress and the result back
    data = read_image(image)  # The image
    return stream_events(lambda: check_image(data))  # The full check
