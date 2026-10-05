import { useCallback, useState } from "react";
import { uploadLabel, type LabelResponse } from "../api/client";
import { useApp } from "../state/AppContext";

export function LabelsPage() {
  const { role } = useApp();
  const [drag, setDrag] = useState(false);
  const [result, setResult] = useState<LabelResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const run = useCallback(
    async (file: File) => {
      setLoading(true);
      setError(null);
      try {
        const res = await uploadLabel(role, file);
        setResult(res);
      } catch (e) {
        setError(e instanceof Error ? e.message : String(e));
      } finally {
        setLoading(false);
      }
    },
    [role],
  );

  return (
    <div className="grid-2">
      <section className="panel stack">
        <h2>Label recognition</h2>
        <p>PDF / PNG / JPEG / WEBP / TIFF → OCR extract → GraphRAG policy check (same LLM).</p>
        <div
          className={`dropzone ${drag ? "active" : ""}`}
          onDragOver={(e) => {
            e.preventDefault();
            setDrag(true);
          }}
          onDragLeave={() => setDrag(false)}
          onDrop={(e) => {
            e.preventDefault();
            setDrag(false);
            const f = e.dataTransfer.files[0];
            if (f) void run(f);
          }}
        >
          <p>Drop a label file here or choose below</p>
          <input
            type="file"
            accept=".png,.jpg,.jpeg,.webp,.tif,.tiff,.pdf,.txt"
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) void run(f);
            }}
          />
        </div>
        {loading && <p>Processing…</p>}
        {error && <p className="error">{error}</p>}
      </section>
      <section className="panel stack">
        <h3>Result</h3>
        {!result && <p>No upload yet.</p>}
        {result && (
          <>
            <div className="row">
              <span className="badge">{result.llm_provider}</span>
              <span className="badge">{result.model_uri}</span>
              {result.degraded && <span className="badge warn">degraded</span>}
            </div>
            <div className="citation">
              <strong>Extract</strong>
              <pre className="mono">{JSON.stringify(result.extract, null, 2)}</pre>
            </div>
            <div className="msg">
              <strong>Grounded answer</strong>
              <div>{result.answer}</div>
            </div>
            <div className="mono">
              raw: {result.s3_uri_raw}
              {"\n"}
              recognized: {result.s3_uri_recognized}
            </div>
            {result.warnings.map((w) => (
              <span key={w} className="badge warn">
                {w}
              </span>
            ))}
          </>
        )}
      </section>
    </div>
  );
}
