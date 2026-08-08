# Job-Application Agent — v2 update

This replaces the paste-text version with a file-upload workflow: upload your
CV (PDF or DOCX), paste a job description, review suggested bullet rewrites
with accept/reject toggles, and download a tailored `.docx` with only the
changes you approved — your original formatting untouched.

## What's new vs. the original starter

- **CV upload, not paste.** `cv_parser.py` reads PDF (via pdfplumber) or DOCX
  (via python-docx). For DOCX, it also records each bullet's exact paragraph
  index — the handle used later to edit that one paragraph in place.
- **Real 3-step pipeline** (`agent.py`): extract requirements → assess fit +
  suggest edits to your *actual* existing bullets → optional company-page
  fetch → generate cover letter/outreach. Suggestions the model returns are
  cross-checked against your real bullet list — a hallucinated or invalid
  paragraph index is dropped, never trusted blindly.
- **Company research tool use** (`tools.py`): a single best-effort HTTP GET
  to a URL you paste (e.g. a company's About page). No crawling, no auth,
  fails gracefully — if the site blocks it or is empty, the pipeline just
  proceeds without that context.
- **CV regeneration** (`cv_generator.py`): edits only the accepted bullets'
  text runs in place, so fonts/spacing/bullets stay exactly as in your
  original file. DOCX in → DOCX out only (no PDF export) — that was a
  deliberate call to avoid a LibreOffice dependency, which would have
  roughly doubled the Docker image size and risked hitting Render's free
  512MB RAM tier.

## Run it locally

```bash
# Backend — mock mode, no API key needed
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
MOCK_LLM=1 uvicorn app.main:app --reload --port 8000

# Frontend (new terminal)
cd frontend
npm install
npm run dev
```

Open http://localhost:5173, upload a `.docx` or `.pdf` CV, paste a job
description, hit Analyze. Everything works in mock mode — no API key
required to see the full flow end to end.

## Run it for real

```bash
export ANTHROPIC_API_KEY=sk-ant-...
export MOCK_LLM=0
cd backend && uvicorn app.main:app --reload --port 8000
```

Get a key at console.anthropic.com — pay-as-you-go, not a subscription. This
app's calls are cheap: a few short prompts per analysis, realistically cents
per run even while testing heavily.

## What's tested

Both endpoints (`/api/analyze`, `/api/generate-cv`) were tested via real
HTTP requests (not just Python import tests) against a real CV file,
including error paths: wrong file type, PDF uploaded to generate-cv
(correctly rejected — regeneration needs the original .docx), and an
out-of-range paragraph index (correctly rejected with a clear message).
The frontend was verified with a real `vite build` (clean, no errors) and a
running dev server. Not yet tested: full click-through in an actual browser,
and a real (non-mock) LLM call — both worth doing once you've got this
running locally with an API key.

## Live Demo
- App: https://job-agent-three-eosin.vercel.app
- Backend API: https://job-agent-wjq3.onrender.com
- Repo: https://github.com/Vedk08/job-agent