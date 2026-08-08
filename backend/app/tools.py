"""A single tool the agent can use: fetch one company URL and return its
readable text. Deliberately minimal — no crawling, no following links, no
JS rendering. One GET request to exactly the URL the user pasted.

This is explicitly best-effort. Many sites block non-browser requests,
render their content client-side (empty HTML on a plain GET), or just
time out. All of those are treated as "no company context available," not
as errors that should break the analysis — see agent.py's usage of this.
"""
import re
from dataclasses import dataclass
from typing import Optional

import httpx

MAX_CHARS = 4000  # keep prompt size sane; About/careers pages don't need more
TIMEOUT_SECONDS = 6.0
USER_AGENT = "Mozilla/5.0 (compatible; JobApplicationAgent/0.1; +portfolio-project)"


@dataclass
class CompanyFetchResult:
    ok: bool
    text: Optional[str]  # None when ok is False
    reason: Optional[str]  # short human-readable failure reason when ok is False


def _strip_html(html: str) -> str:
    """Very small HTML-to-text: drop script/style blocks, strip tags,
    collapse whitespace. Not a real HTML parser — deliberately simple,
    since we only need rough readable text for the LLM, not structure.
    """
    html = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", html)
    text = re.sub(r"(?s)<[^>]+>", " ", html)
    text = re.sub(r"&nbsp;", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def fetch_company_page(url: str) -> CompanyFetchResult:
    """Best-effort fetch of a single company page.

    Returns ok=False (never raises) on any failure — blocked, timed out,
    non-HTML, empty after stripping (common on JS-rendered sites), etc.
    Callers should treat ok=False as "proceed without company context."
    """
    if not url or not url.strip():
        return CompanyFetchResult(ok=False, text=None, reason="No URL provided")

    url = url.strip()
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    try:
        response = httpx.get(
            url,
            headers={"User-Agent": USER_AGENT},
            timeout=TIMEOUT_SECONDS,
            follow_redirects=True,
        )
    except httpx.RequestError as e:
        return CompanyFetchResult(ok=False, text=None, reason=f"Request failed: {e}")

    if response.status_code != 200:
        return CompanyFetchResult(
            ok=False, text=None, reason=f"Site returned HTTP {response.status_code}"
        )

    content_type = response.headers.get("content-type", "")
    if "text/html" not in content_type and "text/plain" not in content_type:
        return CompanyFetchResult(ok=False, text=None, reason="Response wasn't readable text/HTML")

    text = _strip_html(response.text)
    if len(text) < 100:
        # Very short after stripping usually means a JS-rendered shell with
        # no server-side content — nothing useful to give the LLM.
        return CompanyFetchResult(
            ok=False, text=None, reason="Page had little to no readable content (likely JS-rendered)"
        )

    return CompanyFetchResult(ok=True, text=text[:MAX_CHARS], reason=None)
