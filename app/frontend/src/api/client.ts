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
  ocr_provider?: string;
};

const API_BASE = (import.meta.env.VITE_API_BASE_URL || "/api").replace(/\/$/, "");

export type AuthMode = "demo" | "oidc";

export type Me = {
  user_id: string;
  username: string;
  role: string;
  allowed_classifications: string[];
  csrf_token: string;
};

/** Demo mode only: the role key sent as the bearer value. Under OIDC the browser holds no credential but the cookie. */
let demoRole: RoleKey | null = null;
/** OIDC mode only: sent on state-changing requests. Kept in memory, never in storage. */
let csrfToken = "";
let onSessionLost: () => void = () => {};

export function setDemoRole(role: RoleKey): void {
  demoRole = role;
}

export function setSessionLostHandler(handler: () => void): void {
  onSessionLost = handler;
}

function isStateChanging(method: string): boolean {
  return !["GET", "HEAD", "OPTIONS"].includes(method);
}

async function send(url: string, init: RequestInit = {}): Promise<Response> {
  const method = init.method ?? "GET";
  const headers = new Headers(init.headers);
  if (demoRole) headers.set("Authorization", `Bearer ${demoRole}`);
  else if (csrfToken && isStateChanging(method)) headers.set("X-CSRF-Token", csrfToken);
  const res = await fetch(url, { ...init, method, headers, credentials: "same-origin" });
  if (res.status === 401 && !demoRole) onSessionLost();
  return res;
}

function api(path: string, init?: RequestInit): Promise<Response> {
  return send(`${API_BASE}${path}`, init);
}

function jsonBody(body: unknown): RequestInit {
  return { headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) };
}

/** Public. The UI asks this before login, to choose between the role switcher and the login button. */
export async function getAuthMode(): Promise<AuthMode> {
  const res = await fetch(`${API_BASE}/v1/auth/mode`);
  if (!res.ok) await parseError(res);
  const body: { mode: AuthMode } = await res.json();
  return body.mode;
}

/** Returns null when nobody is signed in. Throws on any other failure, including an account with no role. */
export async function getMe(): Promise<Me | null> {
  const res = await fetch("/auth/me", { credentials: "same-origin" });
  if (res.status === 401) return null;
  if (!res.ok) await parseError(res);
  const me: Me = await res.json();
  csrfToken = me.csrf_token;
  return me;
}

/** A full-page navigation: the login redirects run between the browser, the BFF and Keycloak. */
export function login(): void {
  const returnTo = `${window.location.pathname}${window.location.search}`;
  window.location.assign(`/auth/login?return_to=${encodeURIComponent(returnTo)}`);
}

export async function logout(): Promise<void> {
  const res = await send("/auth/logout", { method: "POST" });
  if (!res.ok) await parseError(res);
  csrfToken = "";
  window.location.assign("/");
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
  const res = await api("/health");
  if (!res.ok) await parseError(res);
  return res.json();
}

export async function getLlmConfig(): Promise<LLMConfig> {
  const res = await api("/v1/llm/config");
  if (!res.ok) await parseError(res);
  return res.json();
}

export async function putLlmConfig(body: {
  provider: string;
  base_url?: string;
  model?: string;
}): Promise<LLMConfig> {
  const res = await api("/v1/llm/config", { method: "PUT", ...jsonBody(body) });
  if (!res.ok) await parseError(res);
  return res.json();
}

export async function probeLlm(): Promise<LLMConfig> {
  const res = await api("/v1/llm/health");
  if (!res.ok) await parseError(res);
  return res.json();
}

/** crypto.randomUUID needs a secure context, and the demo runs on plain http://kp.local. */
export function newSessionId(): string {
  const bytes = crypto.getRandomValues(new Uint8Array(16));
  return Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join("");
}

export async function chat(message: string, sessionId: string, stream = false): Promise<ChatResponse> {
  const res = await api("/v1/chat", {
    method: "POST",
    ...jsonBody({ message, session_id: sessionId, stream }),
  });
  if (!res.ok) await parseError(res);
  return res.json();
}

export async function chatStream(
  message: string,
  sessionId: string,
  onMeta: (meta: Record<string, unknown>) => void,
  onFinal: (data: ChatResponse) => void,
): Promise<void> {
  const res = await api("/v1/chat", {
    method: "POST",
    ...jsonBody({ message, session_id: sessionId, stream: true }),
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

export async function uploadLabel(file: File): Promise<LabelResponse> {
  const fd = new FormData();
  fd.append("file", file, file.name);
  const res = await api("/v1/vision/label", { method: "POST", body: fd });
  if (!res.ok) await parseError(res);
  return res.json();
}

export async function graphStats(): Promise<Record<string, number>> {
  const res = await api("/v1/graph/stats");
  if (!res.ok) await parseError(res);
  return res.json();
}

export type GraphSubgraphNode = {
  id: string;
  label: string;
  kind: string;
  corpus?: string;
  classification?: string;
  entity_type?: string;
};

export type GraphSubgraph = {
  seed: string;
  source: string;
  nodes: GraphSubgraphNode[];
  edges: { source: string; target: string; type: string }[];
};

export async function graphSubgraph(seed = "gluten"): Promise<GraphSubgraph> {
  const q = new URLSearchParams({ seed });
  const res = await api(`/v1/graph/subgraph?${q}`);
  if (!res.ok) await parseError(res);
  return res.json();
}

export async function getOutbox(): Promise<{ events: unknown[] }> {
  const res = await api("/v1/outbox");
  if (!res.ok) await parseError(res);
  return res.json();
}

export async function getAudit(): Promise<{ items: unknown[] }> {
  const res = await api("/v1/audit");
  if (!res.ok) await parseError(res);
  return res.json();
}
