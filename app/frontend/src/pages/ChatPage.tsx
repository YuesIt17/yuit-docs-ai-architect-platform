import { useState } from "react";
import { chat, chatStream, type ChatResponse, type Citation } from "../api/client";
import { useApp } from "../state/AppContext";

type Msg = {
  role: "user" | "assistant";
  text: string;
  citations?: Citation[];
  meta?: { model_uri?: string | null; llm_provider?: string | null; acl?: string; degraded?: boolean };
};

export function ChatPage() {
  const { role, llm } = useApp();
  const [input, setInput] = useState("Какие аллергены у FreshFarm oats?");
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [loading, setLoading] = useState(false);
  const [useStream, setUseStream] = useState(true);
  const [error, setError] = useState<string | null>(null);

  async function send() {
    if (!input.trim() || loading) return;
    setError(null);
    setLoading(true);
    const userMsg: Msg = { role: "user", text: input.trim() };
    setMsgs((m) => [...m, userMsg]);
    try {
      if (useStream) {
        let meta: Record<string, unknown> = {};
        await chatStream(
          role,
          userMsg.text,
          (m) => {
            meta = m;
          },
          (data) => {
            setMsgs((prev) => [
              ...prev,
              {
                role: "assistant",
                text: data.answer,
                citations: data.citations,
                meta: {
                  model_uri: data.model_uri ?? (meta.model_uri as string),
                  llm_provider: data.llm_provider ?? (meta.llm_provider as string) ?? llm?.provider,
                  acl: data.acl_decision,
                  degraded: data.degraded,
                },
              },
            ]);
          },
        );
      } else {
        const data: ChatResponse = await chat(role, userMsg.text, false);
        setMsgs((prev) => [
          ...prev,
          {
            role: "assistant",
            text: data.answer,
            citations: data.citations,
            meta: {
              model_uri: data.model_uri,
              llm_provider: data.llm_provider ?? llm?.provider,
              acl: data.acl_decision,
              degraded: data.degraded,
            },
          },
        ]);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="grid-2">
      <section className="panel stack">
        <h2>GraphRAG Chat</h2>
        <p>Запросы идут в Control Plane API → активный LLM ({llm?.provider ?? "…"}).</p>
        <div className="stack">
          {msgs.map((m, i) => (
            <div key={i} className={`msg ${m.role}`}>
              <div className="row" style={{ marginBottom: 6 }}>
                <strong>{m.role === "user" ? "You" : "Assistant"}</strong>
                {m.meta?.llm_provider && <span className="badge">{m.meta.llm_provider}</span>}
                {m.meta?.model_uri && <span className="badge">{m.meta.model_uri}</span>}
                {m.meta?.acl && <span className="badge">{m.meta.acl}</span>}
                {m.meta?.degraded && <span className="badge warn">degraded</span>}
              </div>
              <div>{m.text}</div>
              {m.citations && m.citations.length > 0 && (
                <div className="citations" style={{ marginTop: 10 }}>
                  {m.citations.map((c) => (
                    <div key={c.chunk_id} className="citation">
                      <div className="row">
                        <span className="badge">{c.classification}</span>
                        <span className="mono">{c.doc_id}</span>
                      </div>
                      <div>{c.snippet}</div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
        <label className="field">
          Message
          <textarea value={input} onChange={(e) => setInput(e.target.value)} />
        </label>
        <div className="row">
          <label className="row" style={{ color: "var(--muted)" }}>
            <input type="checkbox" checked={useStream} onChange={(e) => setUseStream(e.target.checked)} />
            SSE stream
          </label>
          <button onClick={() => void send()} disabled={loading}>
            {loading ? "Thinking…" : "Ask"}
          </button>
        </div>
        {error && <p className="error">{error}</p>}
      </section>
      <aside className="panel stack">
        <h3>Try ACL</h3>
        <p>Как manager спросите про «Q4 Closed Promo Margin 42%» — secret не должен утечь. Как compliance — должен.</p>
        <button
          className="secondary"
          onClick={() => setInput("Расскажи про Q4 Closed Promo Margin Playbook и маржу 42%")}
        >
          Secret promo prompt
        </button>
        <button className="secondary" onClick={() => setInput("Что говорит политика про аллергены gluten и nuts?")}>
          Allergen policy prompt
        </button>
      </aside>
    </div>
  );
}
