import { Link } from "react-router-dom";
import { useApp } from "../state/AppContext";

export function LlmStatusPill() {
  const { llm } = useApp();
  if (!llm) {
    return (
      <Link to="/llm" className="badge warn">
        <span className="pill-dot" /> LLM unknown
      </Link>
    );
  }
  const cls = llm.reachable ? "good" : llm.provider === "MOCK" ? "good" : "bad";
  return (
    <Link to="/llm" className={`badge ${cls}`} title={llm.detail ?? undefined}>
      <span className="pill-dot" />
      {llm.provider} · {llm.model}
    </Link>
  );
}
