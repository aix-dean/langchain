"""Optional original HTML interface; the Next.js frontend uses only /api routes."""
from fastapi import APIRouter
from fastapi.responses import FileResponse
from app.core.config import ROOT

router = APIRouter(include_in_schema=False)
STATIC_DIR = ROOT / "static"

@router.get("/")
def index():  # Sends the web page to the browser
    return FileResponse(STATIC_DIR / "index.html", headers={"Cache-Control": "no-store"})  # The whole UI is in this one file; never cached, so updates show up on reload

@router.get("/upload")
def upload_page():
    return FileResponse(STATIC_DIR / "upload.html", headers={"Cache-Control": "no-store"})
