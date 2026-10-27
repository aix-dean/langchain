import json
import re
from datetime import datetime
from pathlib import Path
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from app.features.reports.service import build_report
from app.api.documentation import REPORT_RESPONSES, REPORT_DATA_EXAMPLE

router = APIRouter(tags=["reports"])

@router.post(
    "/api/report", summary="Download an image-review PDF report", operation_id="download_report",
    description="Supply the original image and the completed check result with an optional human decision and notes. This generates a report without rerunning the AI check. The data form field is a JSON-encoded object with result, decision (Approve/Revise/Reject), notes and file_name.",
    response_class=Response, responses=REPORT_RESPONSES,
)
def report(image: UploadFile = File(..., description="The same image used for the review."), data: str = Form(..., description="JSON-encoded report input. result is the complete check result object, not just its verdict string.", examples=[REPORT_DATA_EXAMPLE])):  # The image again (the server never stores it) and the result as JSON text
    try:  # The data must be valid JSON
        info = json.loads(data)  # {"result": {...}, "decision": "...", "notes": "...", "file_name": "..."}
    except json.JSONDecodeError:  # Broken data
        raise HTTPException(400, "Invalid report data.")  # Refuse it
    pdf = build_report(  # Build the PDF
        info.get("result") or {},  # The check result
        image.file.read(),  # The ad image
        file_name=str(info.get("file_name") or image.filename or ""),  # Its file name
        decision=str(info.get("decision") or ""),  # Approve / Revise / Reject
        notes=str(info.get("notes") or ""),  # Reviewer notes
    )  # End of report
    stem = re.sub(r"[^\w-]+", "-", Path(image.filename or "ad").stem).strip("-") or "ad"  # Safe version of the image name, e.g. "golden-lager"
    name = f"ASC-prescreen-{stem}-{datetime.now():%Y-%m-%d}.pdf"  # e.g. ASC-prescreen-golden-lager-2026-10-23.pdf
    return Response(pdf, media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="{name}"'})  # Download it
