export type RoleKey = "guest" | "associate" | "manager" | "compliance";

export type Citation = {
  doc_id: string;
  chunk_id: string;
  corpus: string;
  classification: string;
  snippet: string;
  score: number;
};

export type ChatResponse = {
  answer: string;
  citations: Citation[];
  session_id: string;
  request_id: string;
  degraded: boolean;
  acl_decision: string;
  model_uri?: string | null;
  llm_provider?: string | null;
  index_version?: string | null;
};

export type LLMConfig = {
  provider: string;
  base_url: string;
  model: string;
  model_uri: string;
  reachable?: boolean | null;
  detail?: string | null;
  presets?: Record<string, { base_url: string; model: string }>;
};

export type Health = {
  status: string;
  store_backend: string;
  llm_provider: string;
  llm_model?: string | null;
  llm_reachable?: boolean | null;
  index_version: string;
};

export type LabelResponse = {
  asset_id: string;
  extract: {
    brand?: string | null;
    barcode?: string | null;
    allergens: string[];
    ingredients?: string | null;
    net_weight?: string | null;
    confidence: number;
    raw_ocr_text: string;
  };
  warnings: string[];
  citations: Citation[];
  answer: string;
  s3_uri_raw?: string | null;
  s3_uri_recognized?: string | null;
  request_id: string;
  degraded: boolean;
  model_uri?: string | null;
  llm_provider?: string | null;
};

const API_BASE = (import.meta.env.VITE_API_BASE_URL || "/api").replace(/\/$/, "");

function headers(role: RoleKey, json = false): HeadersInit {
  const h: Record<string, string> = { Authorization: `Bearer ${role}` };
  if (json) h["Content-Type"] = "application/json";
  return h;
}

async function parseError(res: Response): Promise<never> {
  let detail = res.statusText;
  try {
    const body = await res.json();
    detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail ?? body);
  } catch {
    /* ignore */
  }
  throw new Error(`${res.status}: ${detail}`);
}

export async function getHealth(): Promise<Health> {
  const res = await fetch(`${API_BASE}/health`);
  if (!res.ok) await parseError(res);
  return res.json();
}

export async function getLlmConfig(role: RoleKey): Promise<LLMConfig> {
  const res = await fetch(`${API_BASE}/v1/llm/config`, { headers: headers(role) });
  if (!res.ok) await parseError(res);
  return res.json();
}

export async function putLlmConfig(
  role: RoleKey,
  body: { provider: string; base_url?: string; model?: string },
): Promise<LLMConfig> {
  const res = await fetch(`${API_BASE}/v1/llm/config`, {
    method: "PUT",
    headers: headers(role, true),
    body: JSON.stringify(body),
  });
  if (!res.ok) await parseError(res);
  return res.json();
}

export async function probeLlm(role: RoleKey): Promise<LLMConfig> {
  const res = await fetch(`${API_BASE}/v1/llm/health`, { headers: headers(role) });
  if (!res.ok) await parseError(res);
  return res.json();
}

export async function chat(
  role: RoleKey,
  message: string,
  stream = false,
): Promise<ChatResponse> {
  const res = await fetch(`${API_BASE}/v1/chat`, {
    method: "POST",
    headers: headers(role, true),
    body: JSON.stringify({ message, stream }),
  });
  if (!res.ok) await parseError(res);
  return res.json();
}

export async function chatStream(
  role: RoleKey,
  message: string,
  onMeta: (meta: Record<string, unknown>) => void,
  onFinal: (data: ChatResponse) => void,
): Promise<void> {
  const res = await fetch(`${API_BASE}/v1/chat`, {
    method: "POST",
    headers: headers(role, true),
    body: JSON.stringify({ message, stream: true }),
  });
  if (!res.ok) await parseError(res);
  const reader = res.body?.getReader();
  if (!reader) throw new Error("No stream body");
  const decoder = new TextDecoder();
  let buf = "";
  let event = "";
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += decoder.decode(value, { stream: true });
    const parts = buf.split("\n");
    buf = parts.pop() ?? "";
    for (const line of parts) {
      if (line.startsWith("event:")) event = line.slice(6).trim();
      else if (line.startsWith("data:")) {
        const data = JSON.parse(line.slice(5).trim());
        if (event === "meta") onMeta(data);
        if (event === "final") onFinal(data as ChatResponse);
      }
    }
  }
}

export async function uploadLabel(role: RoleKey, file: File): Promise<LabelResponse> {
  const fd = new FormData();
  fd.append("file", file, file.name);
  const res = await fetch(`${API_BASE}/v1/vision/label`, {
    method: "POST",
    headers: { Authorization: `Bearer ${role}` },
    body: fd,
  });
  if (!res.ok) await parseError(res);
  return res.json();
}

export async function graphStats(role: RoleKey): Promise<Record<string, number>> {
  const res = await fetch(`${API_BASE}/v1/graph/stats`, { headers: headers(role) });
  if (!res.ok) await parseError(res);
  return res.json();
}

export async function getOutbox(role: RoleKey): Promise<{ events: unknown[] }> {
  const res = await fetch(`${API_BASE}/v1/outbox`, { headers: headers(role) });
  if (!res.ok) await parseError(res);
  return res.json();
}

export async function getAudit(role: RoleKey): Promise<{ items: unknown[] }> {
  const res = await fetch(`${API_BASE}/v1/audit`, { headers: headers(role) });
  if (!res.ok) await parseError(res);
  return res.json();
}
