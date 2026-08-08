"""FastAPI app — the REST interface the React frontend talks to.

Two endpoints do the real work:
  POST /api/analyze       — JD + uploaded CV (PDF or DOCX) -> AnalyzeResponse
  POST /api/generate-cv   — original DOCX + accepted changes -> edited DOCX

Both take the CV as a real file upload (multipart/form-data), not JSON text
— see models.py for why AnalyzeRequest/GenerateCVRequest don't carry the CV
themselves. FastAPI can't mix a Pydantic JSON body with a file in one
request, so the non-file fields travel as individual Form(...) fields
(generate-cv's accepted_changes travels as a JSON string in one Form field,
parsed manually) alongside the UploadFile.
"""
import json
import os

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

from .agent import analyze as run_agent
from .cv_generator import BulletChange, CVGenerationError, generate_cv
from .cv_parser import parse_cv
from .models import AcceptedBulletChange, AnalyzeResponse

app = FastAPI(title="Job-Application Agent", version="0.2.0")

# Allow the local Vite dev server + any deployed frontend you set via env.
origins = ["http://localhost:5173", "http://127.0.0.1:5173"]
extra = os.getenv("FRONTEND_ORIGIN")
if extra:
    origins.append(extra)

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

ALLOWED_CV_EXTENSIONS = (".pdf", ".docx")
MAX_CV_BYTES = 5 * 1024 * 1024  # 5MB — CVs are small; guards against abuse


def _read_and_validate_cv(cv_file: UploadFile) -> bytes:
    filename = (cv_file.filename or "").lower()
    if not filename.endswith(ALLOWED_CV_EXTENSIONS):
        raise HTTPException(400, "CV must be a .pdf or .docx file.")

    data = cv_file.file.read()
    if len(data) > MAX_CV_BYTES:
        raise HTTPException(400, "CV file is too large (5MB limit).")
    if not data:
        raise HTTPException(400, "Uploaded CV file is empty.")
    return data


@app.get("/api/health")
def health():
    return {"status": "ok", "mock": os.getenv("MOCK_LLM", "0") == "1"}


@app.post("/api/analyze", response_model=AnalyzeResponse)
def analyze_endpoint(
    job_description: str = Form(..., min_length=20),
    tone: str = Form("professional"),
    output_language: str = Form("English"),
    company_url: str | None = Form(None),
    cv_file: UploadFile = File(...),
):
    cv_bytes = _read_and_validate_cv(cv_file)

    try:
        parsed_cv = parse_cv(cv_file.filename, cv_bytes)
    except ValueError as e:
        raise HTTPException(400, str(e))

    try:
        return run_agent(job_description, parsed_cv, tone, output_language, company_url)
    except KeyError:
        raise HTTPException(500, "ANTHROPIC_API_KEY not set (or use MOCK_LLM=1).")
    except json.JSONDecodeError:
        raise HTTPException(500, "The model's response wasn't valid JSON — try again.")
    except Exception as e:  # noqa: BLE001 — surface a clean message to the UI
        raise HTTPException(500, f"Analysis failed: {e}")


@app.post("/api/generate-cv")
def generate_cv_endpoint(
    accepted_changes: str = Form(..., description="JSON array of {paragraph_index, new_text}"),
    cv_file: UploadFile = File(..., description="The ORIGINAL cv.docx — same file used in /api/analyze"),
):
    filename = (cv_file.filename or "").lower()
    if not filename.endswith(".docx"):
        # Regeneration is DOCX-only by design (see cv_generator.py) — a PDF
        # original can be analyzed but not edited in place.
        raise HTTPException(
            400,
            "CV generation requires the original .docx file — PDF-sourced "
            "CVs can be analyzed but not regenerated.",
        )

    cv_bytes = _read_and_validate_cv(cv_file)

    try:
        changes_raw = json.loads(accepted_changes)
        changes = [BulletChange(**AcceptedBulletChange(**c).model_dump()) for c in changes_raw]
    except (json.JSONDecodeError, TypeError, ValueError) as e:
        raise HTTPException(400, f"Invalid accepted_changes payload: {e}")

    if not changes:
        raise HTTPException(400, "No accepted changes were provided.")

    try:
        result = generate_cv(cv_bytes, changes)
    except CVGenerationError as e:
        raise HTTPException(400, str(e))

    return Response(
        content=result["docx"],
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": 'attachment; filename="tailored_cv.docx"'},
    )
