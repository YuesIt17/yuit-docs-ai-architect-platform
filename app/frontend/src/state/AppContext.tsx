import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import {
  getAuthMode,
  getLlmConfig,
  getMe,
  setDemoRole,
  setSessionLostHandler,
  type AuthMode,
  type LLMConfig,
  type Me,
  type RoleKey,
} from "../api/client";

/**
 * loading: the auth mode or session is not known yet.
 * anonymous: OIDC mode with no session.
 * denied: signed in, but the API refuses the account, such as one with no platform role.
 * unavailable: the auth mode or session could not be read.
 * ready: requests can be made.
 */
export type AuthStatus = "loading" | "anonymous" | "denied" | "unavailable" | "ready";

const DEFAULT_DEMO_ROLE: RoleKey = "manager";

type AppContextValue = {
  authMode: AuthMode | null;
  authStatus: AuthStatus;
  authDetail: string | null;
  /** The effective identity. Pages list it as an effect dependency, to reload when it changes. */
  role: string;
  me: Me | null;
  setRole: (r: RoleKey) => void;
  llm: LLMConfig | null;
  refreshLlm: () => Promise<void>;
  setLlm: (c: LLMConfig) => void;
};

const Ctx = createContext<AppContextValue | null>(null);

export function AppProvider({ children }: { children: ReactNode }) {
  const [authMode, setAuthMode] = useState<AuthMode | null>(null);
  const [authStatus, setAuthStatus] = useState<AuthStatus>("loading");
  const [authDetail, setAuthDetail] = useState<string | null>(null);
  const [demoRole, setDemoRoleState] = useState<RoleKey>(DEFAULT_DEMO_ROLE);
  const [me, setMe] = useState<Me | null>(null);
  const [llm, setLlm] = useState<LLMConfig | null>(null);

  useEffect(() => {
    setSessionLostHandler(() => {
      setMe(null);
      setAuthStatus("anonymous");
    });
    void (async () => {
      try {
        const mode = await getAuthMode();
        setAuthMode(mode);
        if (mode === "demo") {
          setDemoRole(DEFAULT_DEMO_ROLE);
          setAuthStatus("ready");
          return;
        }
        const current = await getMe();
        setMe(current);
        setAuthStatus(current ? "ready" : "anonymous");
      } catch (e) {
        const detail = e instanceof Error ? e.message : String(e);
        setAuthDetail(detail);
        setAuthStatus(detail.startsWith("403") ? "denied" : "unavailable");
      }
    })();
  }, []);

  const setRole = useCallback((r: RoleKey) => {
    setDemoRole(r);
    setDemoRoleState(r);
  }, []);

  const role = authMode === "oidc" ? (me?.role ?? "") : demoRole;

  // `role` makes a role switch reload the config. The request itself reads the current credential.
  const refreshLlm = useCallback(async () => {
    try {
      setLlm(await getLlmConfig());
    } catch {
      setLlm(null);
    }
  }, [role]);

  useEffect(() => {
    if (authStatus !== "ready") return;
    void refreshLlm();
    const id = window.setInterval(() => void refreshLlm(), 15000);
    return () => window.clearInterval(id);
  }, [authStatus, refreshLlm]);

  const value = useMemo(
    () => ({ authMode, authStatus, authDetail, role, me, setRole, llm, refreshLlm, setLlm }),
    [authMode, authStatus, authDetail, role, me, setRole, llm, refreshLlm],
  );

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useApp(): AppContextValue {
  const v = useContext(Ctx);
  if (!v) throw new Error("useApp outside provider");
  return v;
}
