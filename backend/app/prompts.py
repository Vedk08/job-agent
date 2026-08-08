"""Prompt templates for the agent pipeline.

The pipeline now runs in THREE steps (up from two), with an optional tool
call between steps 2 and 3:

  Step 1 (extract):     pull discrete requirements out of the job description.
  Step 2 (assess):      score fit + propose edits to the candidate's ACTUAL
                         existing bullets (by index — see cv_parser.py).
  [optional tool call]: if the user gave a company URL, fetch_company_page()
                         tries to pull real context (see tools.py). Best
                         effort — the pipeline proceeds fine without it.
  Step 3 (generate):     write the cover letter + outreach note, using the
                         company context if we got any.

Splitting cover-letter generation into its own step (rather than one big
step 2+3 call, like the original two-step version) is what makes room for
the tool call to actually matter — step 3's prompt only exists in its
"with company context" form if the tool call succeeded.
"""

EXTRACT_REQUIREMENTS = """You are an expert technical recruiter.
Read the job description below and extract the concrete requirements a candidate
is evaluated on. Separate must-haves from nice-to-haves.

Return ONLY a JSON array of strings, no prose, no markdown fences. Example:
["Strong Python", "Experience with REST APIs", "German is a plus"]

JOB DESCRIPTION:
{job_description}
"""

ASSESS_AND_SUGGEST = """You are a sharp, honest career coach helping a candidate
apply for a specific role. You never invent experience the candidate does not have.

REQUIREMENTS (extracted from the job description):
{requirements}

CANDIDATE CV (full text, for context):
{cv_text}

CANDIDATE'S EXISTING BULLETS (only these may be rewritten — see below):
{existing_bullets}

Each existing bullet above is given as a JSON object like
{{"paragraph_index": 16, "section_heading": "...", "text": "..."}}.

Do all of the following and return ONE JSON object with EXACTLY these keys:

- "fit_score": integer 0-100, an honest overall match score.
- "summary": one short paragraph — the honest read, including the biggest gap.
- "matches": array of objects {{"requirement": str, "status": "met"|"partial"|"gap", "evidence": str}}.
  Use the CV as the only source of truth. If something isn't in the CV, it's a gap — do not assume it.
- "bullet_suggestions": array of objects {{"paragraph_index": int, "suggested_text": str}}.
  Pick 3-5 of the MOST relevant existing bullets (by paragraph_index, copied exactly
  from the list above — never invent a paragraph_index that wasn't given to you) and
  rewrite each to speak more directly to this job's requirements. Ground every
  rewrite ONLY in facts already present in that bullet or elsewhere in the CV —
  you are re-emphasizing and re-wording real experience, never adding claims,
  numbers, or tools that aren't already evidenced in the CV.

Return ONLY the JSON object. No markdown fences, no commentary.
"""

GENERATE_OUTREACH = """You are a sharp, honest career coach writing the final
outreach assets for a candidate applying to a specific role. You never invent
experience the candidate does not have.

JOB REQUIREMENTS:
{requirements}

CANDIDATE FIT SUMMARY (already computed):
{summary}

CANDIDATE CV:
{cv_text}

DESIRED COVER-LETTER TONE: {tone}
WRITE THE COVER LETTER AND OUTREACH MESSAGE IN: {output_language}
(This may differ from the job description's language — always follow this
instruction for output language, regardless of what language other inputs
above are written in.)
{company_context_block}
Return ONE JSON object with EXACTLY these keys:
- "cover_letter": a concise cover letter (max ~200 words) in the requested tone,
  no invented facts.{company_instruction}
- "outreach_message": a short (<80 word) LinkedIn/email note to a human at the company.{company_instruction}

Return ONLY the JSON object. No markdown fences, no commentary.
"""

# Filled in only when a company URL was fetched successfully (see agent.py).
COMPANY_CONTEXT_BLOCK = """
COMPANY CONTEXT (fetched from the company's own site — use it to make the
outreach specific and genuine, never generic filler):
{company_text}
"""

COMPANY_INSTRUCTION = (
    " Naturally reference one concrete, specific detail from the company"
    " context above — do not just say 'I admire your mission.'"
)
