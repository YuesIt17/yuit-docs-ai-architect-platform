import { useEffect, useState } from "react";
import { getAudit, getHealth, type Health } from "../api/client";
import { useApp } from "../state/AppContext";

/** Hybrid deep links — Compose LGTM + K8s NodePorts. */
const OPS_LINKS: { title: string; href: string; note: string }[] = [
  {
    title: "Grafana — KP Overview",
    href: "http://localhost:3000/d/kp-overview",
    note: "compose :3000 · dashboard",
  },
  {
    title: "Grafana Explore — Tempo",
    href: "http://localhost:3000/explore?orgId=1&left=%7B%22datasource%22:%22tempo%22%7D",
    note: "traces · service kp-api",
  },
  {
    title: "Grafana Explore — Loki",
    href: "http://localhost:3000/explore?orgId=1&left=%7B%22datasource%22:%22loki%22%7D",
    note: "logs · JSON + trace_id",
  },
  {
    title: "Prometheus targets",
    href: "http://localhost:9090/targets",
    note: "compose :9090 · kp-api-k8s",
  },
  {
    title: "Tempo ready",
    href: "http://localhost:3200/ready",
    note: "compose :3200 · OTLP :4317/:4318",
  },
  {
    title: "Loki ready",
    href: "http://localhost:3100/ready",
    note: "compose :3100",
  },
  {
    title: "Neo4j Browser",
    href: "http://localhost:30474",
    note: "k8s NodePort :30474",
  },
  {
    title: "MinIO Console",
    href: "http://localhost:30901",
    note: "k8s NodePort :30901 · minioadmin",
  },
  {
    title: "API /metrics",
    href: "http://localhost:30080/metrics",
    note: "k8s NodePort :30080",
  },
];

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
        <h3>Deep links (hybrid)</h3>
        <p>
          Compose LGTM: Grafana / Prometheus / Loki / Tempo. K8s NodePort: Neo4j / MinIO / API metrics. Нужен
          side-stack <code>make obs</code> + Desktop Helm.
        </p>
        <ul className="ops-links">
          {OPS_LINKS.map((link) => (
            <li key={link.href}>
              <div>
                <strong>{link.title}</strong> <span className="badge">{link.note}</span>
              </div>
              <a className="ops-link" href={link.href} target="_blank" rel="noreferrer">
                {link.href}
              </a>
            </li>
          ))}
        </ul>
      </section>
      <section className="panel stack">
        <h3>Audit (last)</h3>
        <pre className="mono">{JSON.stringify(audit.slice(0, 15), null, 2)}</pre>
      </section>
    </div>
  );
}
