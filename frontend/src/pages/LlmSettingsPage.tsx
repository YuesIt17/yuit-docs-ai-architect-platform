import { useEffect, useState } from "react";
import { probeLlm, putLlmConfig } from "../api/client";
import { useApp } from "../state/AppContext";

const PROVIDERS = ["MOCK", "OLLAMA", "VLLM"] as const;

export function LlmSettingsPage() {
  const { role, llm, setLlm, refreshLlm } = useApp();
  const [provider, setProvider] = useState("MOCK");
  const [baseUrl, setBaseUrl] = useState("");
  const [model, setModel] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!llm) return;
    setProvider(llm.provider);
    setBaseUrl(llm.base_url);
    setModel(llm.model);
  }, [llm]);

  function applyPreset(p: string) {
    setProvider(p);
    const preset = llm?.presets?.[p];
    if (preset) {
      setBaseUrl(preset.base_url);
      setModel(preset.model);
    }
  }

  async function onProbe() {
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      // Apply draft locally via PUT only on Apply; probe current runtime
      const res = await probeLlm(role);
      setLlm(res);
      setMessage(res.reachable ? `Reachable: ${res.detail}` : `Unreachable: ${res.detail}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  async function onApply() {
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      const res = await putLlmConfig(role, {
        provider,
        base_url: baseUrl,
        model,
      });
      setLlm(res);
      setMessage(`Applied ${res.provider} · ${res.model_uri} · ${res.reachable ? "up" : "down"}`);
      await refreshLlm();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="grid-2">
      <section className="panel stack">
        <h2>LLM Settings</h2>
        <p>
          Frontend управляет provider через Control Plane API. Serving (Ollama/vLLM) остаётся в Data Plane.
          Смена доступна ролям manager / compliance.
        </p>
        <div className="row">
          {PROVIDERS.map((p) => (
            <button key={p} className={provider === p ? "" : "secondary"} type="button" onClick={() => applyPreset(p)}>
              {p}
            </button>
          ))}
        </div>
        <label className="field">
          Provider
          <select value={provider} onChange={(e) => applyPreset(e.target.value)}>
            {PROVIDERS.map((p) => (
              <option key={p} value={p}>
                {p}
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          Base URL (OpenAI-compatible)
          <input value={baseUrl} onChange={(e) => setBaseUrl(e.target.value)} placeholder="http://localhost:11434/v1" />
        </label>
        <label className="field">
          Model
          <input value={model} onChange={(e) => setModel(e.target.value)} placeholder="qwen2.5:0.5b" />
        </label>
        <div className="row">
          <button type="button" className="secondary" disabled={busy} onClick={() => void onProbe()}>
            Probe current
          </button>
          <button type="button" disabled={busy} onClick={() => void onApply()}>
            Apply
          </button>
        </div>
        {message && <p className="success">{message}</p>}
        {error && <p className="error">{error}</p>}
      </section>
      <aside className="panel stack">
        <h3>Active runtime</h3>
        {llm ? (
          <pre className="mono">{JSON.stringify(llm, null, 2)}</pre>
        ) : (
          <p>Loading…</p>
        )}
        <h3>Ollama base URL (куда ходит API, не браузер)</h3>
        <p className="mono">
          make llm-ollama{"\n"}
          Compose API on host: http://localhost:11434/v1{"\n"}
          Compose API in network: http://ollama:11434/v1{"\n"}
          K8s API (Desktop) + Ollama in Compose: http://host.docker.internal:11434/v1
        </p>
        <p>
          Поле Base URL — endpoint <strong>изнутри пода/контейнера API</strong>. Для Helm{" "}
          <code>values-desktop-compose-ollama.yaml</code> значение{" "}
          <code>host.docker.internal</code> нормальное; менять на localhost в UI нельзя — в поде localhost это не
          ваш Ollama.
        </p>
      </aside>
    </div>
  );
}
