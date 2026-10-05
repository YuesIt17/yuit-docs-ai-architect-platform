import { useEffect, useState } from "react";
import { getOutbox, graphStats } from "../api/client";
import { useApp } from "../state/AppContext";

export function GraphPage() {
  const { role } = useApp();
  const [stats, setStats] = useState<Record<string, number> | null>(null);
  const [events, setEvents] = useState<unknown[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void (async () => {
      try {
        setStats(await graphStats(role));
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
  }, [role]);

  return (
    <div className="grid-2">
      <section className="panel stack">
        <h2>Knowledge graph</h2>
        <p>In-memory GraphRAG stats (Neo4j Browser on :7474 when compose is up).</p>
        {error && <p className="error">{error}</p>}
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
