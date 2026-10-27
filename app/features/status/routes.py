from fastapi import APIRouter
from app.features.status.service import status

router = APIRouter(tags=["status"])
router.add_api_route("/api/status", status, methods=["GET"])
