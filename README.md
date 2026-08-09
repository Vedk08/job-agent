# Job-Application Agent

An AI agent that turns a **job description + your CV** into an honest **fit score**,
a **requirement-by-requirement match**, **reviewable tailored CV bullets**, a draft
**cover letter + outreach message**, and a **downloadable regenerated CV** —
served through a REST API and a React UI, with optional company-research tool use.

Built end-to-end: React frontend → FastAPI REST backend → a multi-step LLM agent
pipeline with structured, validated output and tool use → containerised with
Docker → deployed live on Render (backend) and Vercel (frontend).

**Live demo:** https://job-agent-three-eosin.vercel.app
**Backend API:** https://job-agent-wjq3.onrender.com
**Repo:** https://github.com/Vedk08/job-agent

![status](https://img.shields.io/badge/status-live-brightgreen) ![python](https://img.shields.io/badge/python-3.12-blue) ![react](https://img.shields.io/badge/react-18-61dafb)

Built by Vedansh Kumar

---

## What it does

1. **Upload** your CV (PDF or DOCX) and paste a job description.
2. **Extracts** the real requirements from the posting (must-haves vs. nice-to-haves).
3. **Assesses** your CV against each one — `met` / `partial` / `gap` — using the CV as
   the only source of truth. It won't invent experience you don't have, and it says
   so plainly when something's a real gap rather than softening it.
4. **Suggests edits** to your actual existing CV bullets, shown as a reviewable
   diff — accept or reject each one individually.
5. **Optionally researches the company** — give it a URL and it fetches that page
   (best-effort, single request, fails gracefully) to personalize the cover
   letter and outreach note with something real instead of generic filler.
6. **Generates a tailored CV** — a one-click download that applies only the
   bullets you accepted, editing your original `.docx` in place so fonts,
   spacing, and layout stay exactly as they were.

## Architecture

```
React (Vite)  ──HTTP──▶  FastAPI  ──▶  Agent pipeline ──▶  LLM (Anthropic)
  src/App.jsx           app/main.py    app/agent.py         structured JSON
  file upload,          multipart      3 steps + optional    validated by
  diff view, CV         file handling  tool call             Pydantic
  download
```

The agent runs as a **multi-step pipeline** — extract requirements → assess fit
and suggest edits to your real CV bullets (cross-checked against the actual
parsed CV, so a hallucinated suggestion gets dropped, not trusted) → optional
company-page fetch → generate cover letter/outreach, conditioned on whatever
company context was actually found. All LLM output is forced into a JSON
schema and **validated with Pydantic** before it reaches the UI.

## Run it locally (30 seconds, no API key)

```bash
# Backend — MOCK mode returns a realistic canned response
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
MOCK_LLM=1 uvicorn app.main:app --reload      # http://localhost:8000

# Frontend (new terminal)
cd frontend
npm install
npm run dev                                    # http://localhost:5173
```

## Run it for real

```bash
export ANTHROPIC_API_KEY=sk-ant-...   # console.anthropic.com — pay-as-you-go
export MOCK_LLM=0
cd backend && uvicorn app.main:app --reload
```

## Deployment

- **Backend:** Render (Python 3.12 pinned via `PYTHON_VERSION` env var — Render's
  default Python 3.14 doesn't have a prebuilt `pydantic-core` wheel).
  Root directory: `backend`. Start command:
  `uvicorn app.main:app --host 0.0.0.0 --port $PORT`.
- **Frontend:** Vercel, root directory `frontend`, framework preset Vite.
  Set `VITE_API_BASE` to the deployed backend URL.
- Backend needs `FRONTEND_ORIGIN` set to the deployed frontend's exact URL
  (CORS) once the frontend URL is known.

## What this demonstrates

| Skill | Where |
|------|-------|
| React frontend, file upload, reviewable diff UI | `frontend/src/App.jsx` |
| REST API design, multipart file handling, CORS | `backend/app/main.py` |
| Multi-step LLM agent pipeline with tool use | `backend/app/agent.py`, `backend/app/tools.py` |
| Structured output + validation + hallucination guarding | `backend/app/models.py`, `backend/app/agent.py` |
| DOCX parsing and in-place, template-preserving editing | `backend/app/cv_parser.py`, `backend/app/cv_generator.py` |
| Deployment (Render + Vercel), CORS, env config | this README |

## Tested

Every core path was tested with real HTTP requests and, separately, by
clicking through the actual live deployment — not just import tests. That
includes: file upload and parsing against real CVs, the full 3-step agent
pipeline with a real (non-mock) Anthropic API call, the company-research
tool succeeding on a real company URL and visibly personalizing the output,
error paths (wrong file type, PDF uploaded where a DOCX is required,
out-of-range bullet index), and the CV-regeneration download producing a
correctly edited `.docx` with the original formatting intact.

## Level it up (honest next steps)

- A LangGraph-based state machine instead of the current linear pipeline,
  for explicit branching/retry logic.
- Retry-with-fallback if the company-fetch tool call fails, rather than
  just proceeding without context (current behavior is safe but silent).
- A small eval set (JD/CV pairs with expected scores) to catch regressions.
- Automated tests (`pytest` is already a dependency; none written yet).

## License

MIT
