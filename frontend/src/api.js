const BASE = import.meta.env.VITE_API_BASE || "http://localhost:8000";

async function parseErrorDetail(res) {
  try {
    const body = await res.json();
    return body.detail || `Request failed (${res.status})`;
  } catch {
    return `Request failed (${res.status})`;
  }
}

export async function analyze(cvFile, jobDescription, tone = "professional", outputLanguage = "English", companyUrl = "") {
  const form = new FormData();
  form.append("cv_file", cvFile);
  form.append("job_description", jobDescription);
  form.append("tone", tone);
  form.append("output_language", outputLanguage);
  if (companyUrl) form.append("company_url", companyUrl);

  const res = await fetch(`${BASE}/api/analyze`, { method: "POST", body: form });
  if (!res.ok) throw new Error(await parseErrorDetail(res));
  return res.json();
}

// acceptedChanges: [{ paragraph_index, new_text }]
// Returns a Blob (the generated .docx) — caller triggers the browser download.
export async function generateCV(cvFile, acceptedChanges) {
  const form = new FormData();
  form.append("cv_file", cvFile);
  form.append("accepted_changes", JSON.stringify(acceptedChanges));

  const res = await fetch(`${BASE}/api/generate-cv`, { method: "POST", body: form });
  if (!res.ok) throw new Error(await parseErrorDetail(res));
  return res.blob();
}

export function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}
