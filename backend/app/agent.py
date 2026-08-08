"""The agent: a multi-step pipeline that turns a JD + parsed CV into a
structured analysis, with an optional tool call for company research.

Set MOCK_LLM=1 to run the whole app end-to-end WITHOUT an API key (returns a
realistic canned response). That lets you see it working in 30 seconds, then
plug in a real key when you're ready.

Providers: defaults to Anthropic (ANTHROPIC_API_KEY). Swapping to OpenAI is a
small change in `call_llm` — left as a deliberate, well-marked exercise.

Pipeline shape (see prompts.py for the "why three steps" explanation):
  1. extract requirements from the JD
  2. assess fit + suggest edits to the candidate's ACTUAL existing bullets
  3. (optional) fetch company context — best effort, never blocks the pipeline
  4. generate cover letter + outreach, using company context if we got any
"""
import json
import os
import re

from .cv_parser import ParsedCV
from .models import AnalyzeResponse, BulletSuggestion, CVSourceFormat, MatchItem
from .prompts import (
    EXTRACT_REQUIREMENTS,
    ASSESS_AND_SUGGEST,
    GENERATE_OUTREACH,
    COMPANY_CONTEXT_BLOCK,
    COMPANY_INSTRUCTION,
)
from .tools import fetch_company_page

MOCK = os.getenv("MOCK_LLM", "0") == "1"
MODEL = os.getenv("LLM_MODEL", "claude-sonnet-4-6")


def _strip_fences(text: str) -> str:
    """LLMs sometimes wrap JSON in ```json fences despite instructions."""
    text = text.strip()
    text = re.sub(r"^```(?:json)?", "", text).strip()
    text = re.sub(r"```$", "", text).strip()
    return text


def call_llm(prompt: str) -> str:
    """Single LLM call returning raw text. Anthropic by default."""
    if MOCK:
        raise RuntimeError("call_llm should not run in MOCK mode")
    # Imported lazily so the app starts (and MOCK mode works) without the SDK.
    import anthropic

    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    msg = client.messages.create(
        model=MODEL,
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}],
    )
    return msg.content[0].text


def _mock_response(parsed_cv: ParsedCV) -> AnalyzeResponse:
    # Use real bullets from the parsed CV if we have them, so mock mode
    # exercises the same downstream code path (paragraph_index-based
    # suggestions) as the real pipeline — not a fake shortcut.
    suggestions = [
        BulletSuggestion(
            paragraph_index=b.paragraph_index,
            section_heading=b.section_heading,
            original_text=b.text,
            suggested_text=b.text + " (MOCK rewrite — set a real API key to see this properly tailored.)",
        )
        for b in parsed_cv.bullets[:3]
    ]
    return AnalyzeResponse(
        fit_score=78,
        summary=(
            "Strong fit on the core engineering requirements; the main gap is "
            "front-end framework depth, which the JD lists as a 'plus' rather "
            "than a must-have. (This is a MOCK response — set a real API key.)"
        ),
        matches=[
            MatchItem(requirement="Strong Python", status="met",
                      evidence="CV shows multiple Python projects incl. an LLM/RAG system."),
            MatchItem(requirement="REST APIs", status="met",
                      evidence="Built a REST API over a backend datastore."),
            MatchItem(requirement="CI/CD", status="gap",
                      evidence="Not evidenced in the CV — worth adding a pipeline."),
        ],
        bullet_suggestions=suggestions,
        cover_letter=(
            "Dear Hiring Team, I'm applying for your working-student role... "
            "(MOCK cover letter — plug in an API key to generate the real thing.)"
        ),
        outreach_message=(
            "Hi [Name] — CS master's student, just applied for your role. I build "
            "and ship AI tools end-to-end and would love to connect. (MOCK)"
        ),
        cv_source_format=CVSourceFormat(parsed_cv.source_format),
        company_context_used=False,
    )


def _extract_requirements(job_description: str) -> list[str]:
    raw = call_llm(EXTRACT_REQUIREMENTS.format(job_description=job_description))
    try:
        return json.loads(_strip_fences(raw))
    except json.JSONDecodeError:
        return [job_description[:500]]  # graceful fallback


def _assess_and_suggest(requirements: list[str], parsed_cv: ParsedCV) -> dict:
    existing_bullets_json = json.dumps([
        {
            "paragraph_index": b.paragraph_index,
            "section_heading": b.section_heading,
            "text": b.text,
        }
        for b in parsed_cv.bullets
    ], ensure_ascii=False)

    raw = call_llm(ASSESS_AND_SUGGEST.format(
        requirements=json.dumps(requirements, ensure_ascii=False),
        cv_text=parsed_cv.plain_text,
        existing_bullets=existing_bullets_json,
    ))
    return json.loads(_strip_fences(raw))


def _valid_bullet_suggestions(raw_suggestions: list[dict], parsed_cv: ParsedCV) -> list[BulletSuggestion]:
    """Cross-checks the LLM's suggestions against the REAL bullet list.

    The LLM is instructed to only reference paragraph_index values we gave
    it, but instructions aren't guarantees — an LLM can hallucinate an index
    that doesn't exist. We drop (not crash on) any suggestion that doesn't
    match a real bullet, so a single bad index can't corrupt the response
    or, later, cause cv_generator.py to edit the wrong paragraph.
    """
    by_index = {b.paragraph_index: b for b in parsed_cv.bullets}
    suggestions = []
    for item in raw_suggestions:
        idx = item.get("paragraph_index")
        original = by_index.get(idx)
        if original is None:
            continue  # hallucinated or stale index — silently drop
        suggestions.append(BulletSuggestion(
            paragraph_index=idx,
            section_heading=original.section_heading,
            original_text=original.text,
            suggested_text=item.get("suggested_text", original.text),
        ))
    return suggestions


def _generate_outreach(requirements: list[str], summary: str, cv_text: str,
                        tone: str, output_language: str, company_text: str | None) -> dict:
    if company_text:
        context_block = COMPANY_CONTEXT_BLOCK.format(company_text=company_text)
        instruction = COMPANY_INSTRUCTION
    else:
        context_block = ""
        instruction = ""

    raw = call_llm(GENERATE_OUTREACH.format(
        requirements=json.dumps(requirements, ensure_ascii=False),
        summary=summary,
        cv_text=cv_text,
        tone=tone,
        output_language=output_language,
        company_context_block=context_block,
        company_instruction=instruction,
    ))
    return json.loads(_strip_fences(raw))


def analyze(job_description: str, parsed_cv: ParsedCV, tone: str,
            output_language: str = "English", company_url: str | None = None) -> AnalyzeResponse:
    """Runs the full pipeline and returns validated, structured output."""
    if MOCK:
        return _mock_response(parsed_cv)

    # Step 1 — extract requirements from the JD.
    requirements = _extract_requirements(job_description)

    # Step 2 — assess fit + suggest edits to the candidate's real bullets.
    assessment = _assess_and_suggest(requirements, parsed_cv)
    bullet_suggestions = _valid_bullet_suggestions(
        assessment.get("bullet_suggestions", []), parsed_cv
    )

    # Optional tool call — best effort, never blocks the pipeline. A failed
    # or skipped fetch just means step 3 runs without company context.
    company_text = None
    if company_url:
        fetch_result = fetch_company_page(company_url)
        if fetch_result.ok:
            company_text = fetch_result.text

    # Step 3 — generate cover letter + outreach, with company context if any.
    outreach = _generate_outreach(
        requirements=requirements,
        summary=assessment["summary"],
        cv_text=parsed_cv.plain_text,
        tone=tone,
        output_language=output_language,
        company_text=company_text,
    )

    return AnalyzeResponse(
        fit_score=assessment["fit_score"],
        summary=assessment["summary"],
        matches=[MatchItem(**m) for m in assessment["matches"]],
        bullet_suggestions=bullet_suggestions,
        cover_letter=outreach["cover_letter"],
        outreach_message=outreach["outreach_message"],
        cv_source_format=CVSourceFormat(parsed_cv.source_format),
        company_context_used=company_text is not None,
    )
