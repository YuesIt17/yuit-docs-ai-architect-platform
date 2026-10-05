import { useEffect, useState } from "react";
import { getAudit, getHealth, type Health } from "../api/client";
import { useApp } from "../state/AppContext";

export function OpsPage() {
  const { role, llm } = useApp();
  const [health, setHealth] = useState<Health | null>(null);
  const [audit, setAudit] = useState<unknown[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void (async () => {
      try {
        setHealth(await getHealth());
        try {
          const a = await getAudit(role);
          setAudit(a.items ?? []);
        } catch {
          setAudit([]);
        }
      } catch (e) {
        setError(e instanceof Error ? e.message : String(e));
      }
    })();
  }, [role]);

  return (
    <div className="grid-2">
      <section className="panel stack">
        <h2>Ops</h2>
        {error && <p className="error">{error}</p>}
        <div className="row">
          <span className={`badge ${health?.llm_reachable || llm?.provider === "MOCK" ? "good" : "bad"}`}>
            LLM {health?.llm_provider ?? llm?.provider}
          </span>
          <span className="badge">{health?.llm_model}</span>
          <span className="badge">index {health?.index_version}</span>
        </div>
        <pre className="mono">{JSON.stringify(health, null, 2)}</pre>
        <h3>Deep links (compose)</h3>
        <ul>
          <li>
            <a href="http://localhost:16686" target="_blank" rel="noreferrer">
              Jaeger
            </a>
          </li>
          <li>
            <a href="http://localhost:3000" target="_blank" rel="noreferrer">
              Grafana
            </a>
          </li>
          <li>
            <a href="http://localhost:7474" target="_blank" rel="noreferrer">
              Neo4j Browser
            </a>
          </li>
          <li>
            <a href="http://localhost:9001" target="_blank" rel="noreferrer">
              MinIO Console
            </a>
          </li>
          <li>
            <a href="http://localhost:8080/metrics" target="_blank" rel="noreferrer">
              Prometheus metrics
            </a>
          </li>
        </ul>
      </section>
      <section className="panel stack">
        <h3>Audit (last)</h3>
        <pre className="mono">{JSON.stringify(audit.slice(0, 15), null, 2)}</pre>
      </section>
    </div>
  );
}
