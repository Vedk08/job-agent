import { useState } from "react";
import { analyze, generateCV, downloadBlob } from "./api";

const STATUS_COLOR = { met: "#1e7d3a", partial: "#b8860b", gap: "#b3261e" };

export default function App() {
  const [cvFile, setCvFile] = useState(null);
  const [jd, setJd] = useState("");
  const [tone, setTone] = useState("professional");
  const [outputLanguage, setOutputLanguage] = useState("English");
  const [companyUrl, setCompanyUrl] = useState("");

  const [result, setResult] = useState(null);
  // Local accept/reject state for suggestions, keyed by paragraph_index.
  // Starts every suggestion as accepted=true — reviewing means unchecking
  // the ones you DON'T want, which matches how most people will actually
  // use this (accept most, reject a couple).
  const [acceptedMap, setAcceptedMap] = useState({});

  const [loading, setLoading] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState("");

  function onFileChange(e) {
    const file = e.target.files?.[0] || null;
    setCvFile(file);
    setResult(null);
    setError("");
  }

  async function onAnalyze() {
    setLoading(true);
    setError("");
    setResult(null);
    try {
      const data = await analyze(cvFile, jd, tone, outputLanguage, companyUrl);
      setResult(data);
      const initial = {};
      for (const s of data.bullet_suggestions) initial[s.paragraph_index] = true;
      setAcceptedMap(initial);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  function toggleAccepted(paragraphIndex) {
    setAcceptedMap((prev) => ({ ...prev, [paragraphIndex]: !prev[paragraphIndex] }));
  }

  async function onGenerateCV() {
    const changes = result.bullet_suggestions
      .filter((s) => acceptedMap[s.paragraph_index])
      .map((s) => ({ paragraph_index: s.paragraph_index, new_text: s.suggested_text }));

    if (changes.length === 0) {
      setError("Accept at least one suggested change before generating a CV.");
      return;
    }

    setGenerating(true);
    setError("");
    try {
      const blob = await generateCV(cvFile, changes);
      downloadBlob(blob, "tailored_cv.docx");
    } catch (e) {
      setError(e.message);
    } finally {
      setGenerating(false);
    }
  }

  const canGenerate = result?.cv_source_format === "docx" && result?.bullet_suggestions?.length > 0;
  const canAnalyze = !loading && cvFile && jd.length >= 20;

  return (
    <div className="wrap">
      <header>
        <h1>Job-Application Agent</h1>
        <p className="sub">
          Upload your CV, paste a job description — get an honest fit score, reviewable
          bullet rewrites, a draft cover letter, and an outreach note.
        </p>
      </header>

      <section className="inputs">
        <div className="field">
          <label>Your CV (.pdf or .docx)</label>
          <input type="file" accept=".pdf,.docx" onChange={onFileChange} />
          {cvFile && <p className="hint">{cvFile.name}</p>}
          {cvFile && !cvFile.name.toLowerCase().endsWith(".docx") && (
            <p className="hint">
              PDF CVs can be analyzed, but the "Generate CV" step needs a .docx to edit in place.
            </p>
          )}
        </div>
        <div className="field">
          <label>Job description</label>
          <textarea value={jd} onChange={(e) => setJd(e.target.value)} placeholder="Paste the posting…" />
        </div>
      </section>

      <div className="field">
        <label>Company URL (optional — best effort, may not work for every site)</label>
        <input
          type="text"
          value={companyUrl}
          onChange={(e) => setCompanyUrl(e.target.value)}
          placeholder="https://company.com/about"
        />
      </div>

      <div className="controls">
        <label>
          Tone:&nbsp;
          <select value={tone} onChange={(e) => setTone(e.target.value)}>
            <option value="professional">Professional</option>
            <option value="warm">Warm</option>
            <option value="direct">Direct</option>
          </select>
        </label>
        <label>
          Language:&nbsp;
          <select value={outputLanguage} onChange={(e) => setOutputLanguage(e.target.value)}>
            <option value="English">English</option>
            <option value="German">German</option>
          </select>
        </label>
        <button onClick={onAnalyze} disabled={!canAnalyze}>
          {loading ? "Analyzing…" : "Analyze"}
        </button>
      </div>

      {error && <p className="error">{error}</p>}

      {result && (
        <section className="results">
          <div className="score">
            <span className="num">{result.fit_score}</span>
            <span className="lbl">/ 100 fit</span>
          </div>
          <p className="summary">{result.summary}</p>
          {result.company_context_used && (
            <p className="hint">✓ Personalized using company context from the URL you gave.</p>
          )}

          <h2>Requirement match</h2>
          <ul className="matches">
            {result.matches.map((m, i) => (
              <li key={i}>
                <span className="dot" style={{ background: STATUS_COLOR[m.status] }} />
                <strong>{m.requirement}</strong> — <em>{m.status}</em>
                <div className="ev">{m.evidence}</div>
              </li>
            ))}
          </ul>

          <h2>Suggested CV changes</h2>
          <p className="hint">Review each one — uncheck any you don't want before generating a new CV.</p>
          <ul className="suggestions">
            {result.bullet_suggestions.map((s) => (
              <li key={s.paragraph_index} className={acceptedMap[s.paragraph_index] ? "" : "rejected"}>
                <label className="accept-toggle">
                  <input
                    type="checkbox"
                    checked={!!acceptedMap[s.paragraph_index]}
                    onChange={() => toggleAccepted(s.paragraph_index)}
                  />
                  {s.section_heading && <span className="section">{s.section_heading}</span>}
                </label>
                <div className="diff">
                  <div className="orig">− {s.original_text}</div>
                  <div className="new">+ {s.suggested_text}</div>
                </div>
              </li>
            ))}
          </ul>

          {canGenerate && (
            <button className="generate-btn" onClick={onGenerateCV} disabled={generating}>
              {generating ? "Generating…" : "Generate tailored CV (.docx)"}
            </button>
          )}
          {!canGenerate && result.cv_source_format !== "docx" && (
            <p className="hint">Upload a .docx CV to enable generating an edited copy.</p>
          )}

          <h2>Cover letter</h2>
          <pre className="block">{result.cover_letter}</pre>

          <h2>Outreach message</h2>
          <pre className="block">{result.outreach_message}</pre>
        </section>
      )}
    </div>
  );
}
