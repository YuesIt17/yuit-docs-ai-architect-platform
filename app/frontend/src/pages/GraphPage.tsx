import { useEffect, useMemo, useState } from "react";
import { getOutbox, graphStats, graphSubgraph, type GraphSubgraph } from "../api/client";
import { useApp } from "../state/AppContext";

const NEO4J_BROWSER = "http://localhost:30474";

function layoutNodes(sub: GraphSubgraph) {
  const docs = sub.nodes.filter((n) => n.kind === "document");
  const ents = sub.nodes.filter((n) => n.kind === "entity");
  const w = 640;
  const h = 320;
  const pos = new Map<string, { x: number; y: number }>();
  docs.forEach((n, i) => {
    const col = n.corpus === "policy" ? 2 : 0;
    const row = i;
    pos.set(n.id, {
      x: 80 + col * 240,
      y: 40 + row * Math.min(56, (h - 80) / Math.max(docs.length, 1)),
    });
  });
  ents.forEach((n, i) => {
    pos.set(n.id, {
      x: w / 2,
      y: 60 + i * Math.min(70, (h - 100) / Math.max(ents.length, 1)),
    });
  });
  // place any leftover nodes
  sub.nodes.forEach((n, i) => {
    if (!pos.has(n.id)) {
      pos.set(n.id, { x: 40 + (i % 5) * 120, y: h - 40 });
    }
  });
  return { pos, w, h };
}

export function GraphPage() {
  const { role } = useApp();
  const [stats, setStats] = useState<Record<string, number> | null>(null);
  const [sub, setSub] = useState<GraphSubgraph | null>(null);
  const [seed, setSeed] = useState("gluten");
  const [events, setEvents] = useState<unknown[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void (async () => {
      try {
        setError(null);
        setStats(await graphStats(role));
        setSub(await graphSubgraph(role, seed));
        try {
          const ob = await getOutbox(role);
          setEvents(ob.events ?? []);
        } catch {
          setEvents([]);
        }
      } catch (e) {
        setError(e instanceof Error ? e.message : String(e));
      }
    })();
  }, [role, seed]);

  const viz = useMemo(() => (sub ? layoutNodes(sub) : null), [sub]);

  return (
    <div className="grid-2">
      <section className="panel stack">
        <h2>Knowledge graph</h2>
        <p>
          ACL-filtered subgraph (Product → allergen ← Policy). Live Neo4j when store is live;
          otherwise in-memory seed mirror.
        </p>
        <div className="row" style={{ gap: "0.5rem", flexWrap: "wrap" }}>
          <label>
            Seed{" "}
            <input
              className="mono"
              value={seed}
              onChange={(e) => setSeed(e.target.value)}
              list="allergen-seeds"
            />
          </label>
          <datalist id="allergen-seeds">
            <option value="gluten" />
            <option value="nuts" />
            <option value="milk" />
          </datalist>
          <a className="ops-link" href={NEO4J_BROWSER} target="_blank" rel="noreferrer">
            Open Neo4j Browser (:30474)
          </a>
        </div>
        {error && <p className="error">{error}</p>}
        {viz && sub && (
          <svg
            viewBox={`0 0 ${viz.w} ${viz.h}`}
            width="100%"
            style={{ maxHeight: 340, background: "var(--panel-bg, #0f1419)", borderRadius: 8 }}
            role="img"
            aria-label="Knowledge graph subgraph"
          >
            {sub.edges.map((e, i) => {
              const a = viz.pos.get(e.source);
              const b = viz.pos.get(e.target);
              if (!a || !b) return null;
              return (
                <g key={`${e.source}-${e.target}-${i}`}>
                  <line x1={a.x} y1={a.y} x2={b.x} y2={b.y} stroke="#6b7c8f" strokeWidth={1.5} />
                  <text
                    x={(a.x + b.x) / 2}
                    y={(a.y + b.y) / 2 - 4}
                    fill="#9aa8b5"
                    fontSize={9}
                    textAnchor="middle"
                  >
                    {e.type}
                  </text>
                </g>
              );
            })}
            {sub.nodes.map((n) => {
              const p = viz.pos.get(n.id);
              if (!p) return null;
              const fill = n.kind === "entity" ? "#c4783a" : n.corpus === "policy" ? "#3a7a5c" : "#3a5f8a";
              return (
                <g key={n.id}>
                  <rect
                    x={p.x - 56}
                    y={p.y - 14}
                    width={112}
                    height={28}
                    rx={6}
                    fill={fill}
                    opacity={0.9}
                  />
                  <title>{`${n.label} (${n.kind}${n.classification ? ", " + n.classification : ""})`}</title>
                  <text x={p.x} y={p.y + 4} fill="#fff" fontSize={10} textAnchor="middle">
                    {(n.label || n.id).slice(0, 18)}
                  </text>
                </g>
              );
            })}
          </svg>
        )}
        {sub && (
          <p className="mono" style={{ fontSize: "0.85rem" }}>
            source={sub.source} · nodes={sub.nodes.length} · edges={sub.edges.length}
          </p>
        )}
        {stats && (
          <table className="table">
            <tbody>
              {Object.entries(stats).map(([k, v]) => (
                <tr key={k}>
                  <th>{k}</th>
                  <td className="mono">{v}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
      <section className="panel stack">
        <h3>Outbox (PIM handoff)</h3>
        <p>Events after label recognition. Requires manager/compliance.</p>
        <pre className="mono">{JSON.stringify(events, null, 2)}</pre>
      </section>
    </div>
  );
}
