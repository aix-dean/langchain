from fastapi import APIRouter
from app.features.status.service import status
from app.features.status.schemas import StatusResponse

router = APIRouter(tags=["status"])
router.add_api_route(
    "/api/status", status, methods=["GET"], response_model=StatusResponse,
    summary="Check backend and model readiness", operation_id="get_status",
    description="Reports configured models, Ollama/Qdrant availability, missing models, ASC passage count, generation activity and conversation limits. HTTP 200 does not by itself mean all dependencies are ready: inspect the booleans and missing_models. This probe can initialize the vector-store/embedding adapter on first access.",
)
