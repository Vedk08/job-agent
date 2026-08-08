"""Pydantic schemas — the structured contract between the agent, the API, and
the frontend.

Structured output is a core production skill in 2026: the LLM is forced to
return JSON matching these shapes, which we validate before sending to the UI.

Two workflow-shaped design choices worth calling out:

1. CV input is now a FILE (PDF or DOCX), not pasted text — see main.py, which
   accepts multipart/form-data and runs it through cv_parser.py before ever
   touching these models. `AnalyzeRequest` below only covers the JD + tone;
   the file itself is a separate multipart field because Pydantic models
   don't carry file uploads directly in FastAPI.

2. Suggested CV edits are now individually accept/reject-able
   (`BulletSuggestion`), not a flat list of rewritten bullets. The frontend
   renders each one next to the original with a toggle; only the accepted
   ones get sent to /api/generate-cv. `paragraph_index` is the same handle
   cv_parser.py assigns — it's what lets cv_generator.py edit exactly that
   paragraph later, so the two modules share this identifier by contract.
"""
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field


class AnalyzeRequest(BaseModel):
    job_description: str = Field(..., min_length=20, description="Raw job posting text")
    tone: str = Field("professional", description="Tone for the generated cover letter")
    output_language: str = Field(
        "English", description="Language for the cover letter/outreach message, chosen by the user"
    )
    company_url: Optional[str] = Field(
        None, description="Optional company careers/about page URL for personalized outreach"
    )
    # cv_text is intentionally absent — the CV arrives as an uploaded file
    # (multipart field, parsed server-side by cv_parser.py) rather than
    # pasted text, per the CV-upload feature.


class CVSourceFormat(str, Enum):
    docx = "docx"
    pdf = "pdf"


class MatchStatus(str, Enum):
    met = "met"
    partial = "partial"
    gap = "gap"


class MatchItem(BaseModel):
    requirement: str = Field(..., description="A single requirement extracted from the JD")
    status: MatchStatus = Field(..., description="How well the CV covers it")
    evidence: str = Field(..., description="Why — cite the CV, or name what's missing")


class BulletSuggestion(BaseModel):
    """One proposed rewrite of a single existing CV bullet.

    paragraph_index is only present when the uploaded CV was a DOCX — it's
    the handle cv_generator.py needs to edit that exact paragraph in place.
    For a PDF-sourced CV, suggestions are still shown (for reading/copying)
    but paragraph_index is None, since we can't safely regenerate a PDF's
    layout — see cv_generator.py's DOCX-only design.
    """
    paragraph_index: Optional[int] = Field(
        None, description="Edit handle into the original DOCX; null for PDF-sourced CVs"
    )
    section_heading: Optional[str] = Field(
        None, description="Which project/role this bullet belongs to, for display context"
    )
    original_text: str
    suggested_text: str


class AnalyzeResponse(BaseModel):
    fit_score: int = Field(..., ge=0, le=100, description="Overall fit, 0-100")
    summary: str = Field(..., description="One-paragraph honest read on the match")
    matches: List[MatchItem]
    bullet_suggestions: List[BulletSuggestion] = Field(
        ..., description="Proposed per-bullet rewrites, shown with accept/reject toggles"
    )
    cover_letter: str
    outreach_message: str = Field(..., description="Short LinkedIn/email note to a human")
    cv_source_format: CVSourceFormat = Field(
        ..., description="Whether the uploaded CV was docx or pdf — gates the 'Generate CV' button"
    )
    company_context_used: bool = Field(
        False, description="True if company_url was fetched and actually informed the outreach/letter"
    )


class AcceptedBulletChange(BaseModel):
    """One suggestion the user accepted, sent back to /api/generate-cv.

    Only paragraph_index + the final text are needed — the endpoint doesn't
    need original_text or section_heading again, those were just for the
    diff view.
    """
    paragraph_index: int
    new_text: str


class GenerateCVRequest(BaseModel):
    """The JSON part of the generate-cv request.

    The original CV file itself travels alongside this as a separate
    multipart field (see main.py) — same reasoning as AnalyzeRequest not
    carrying cv_text. Re-sending the original file (rather than having the
    backend cache it) keeps the API stateless: no server-side session to
    manage, and no risk of applying changes to a stale cached copy if the
    user re-uploads a slightly edited CV between calls.
    """
    accepted_changes: List[AcceptedBulletChange]
