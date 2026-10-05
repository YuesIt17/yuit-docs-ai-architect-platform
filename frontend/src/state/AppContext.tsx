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
  getLlmConfig,
  type LLMConfig,
  type RoleKey,
} from "../api/client";

type AppContextValue = {
  role: RoleKey;
  setRole: (r: RoleKey) => void;
  llm: LLMConfig | null;
  refreshLlm: () => Promise<void>;
  setLlm: (c: LLMConfig) => void;
};

const Ctx = createContext<AppContextValue | null>(null);

export function AppProvider({ children }: { children: ReactNode }) {
  const [role, setRole] = useState<RoleKey>("manager");
  const [llm, setLlm] = useState<LLMConfig | null>(null);

  const refreshLlm = useCallback(async () => {
    try {
      const cfg = await getLlmConfig(role);
      setLlm(cfg);
    } catch {
      setLlm(null);
    }
  }, [role]);

  useEffect(() => {
    void refreshLlm();
    const id = window.setInterval(() => void refreshLlm(), 15000);
    return () => window.clearInterval(id);
  }, [refreshLlm]);

  const value = useMemo(
    () => ({ role, setRole, llm, refreshLlm, setLlm }),
    [role, llm, refreshLlm],
  );

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useApp(): AppContextValue {
  const v = useContext(Ctx);
  if (!v) throw new Error("useApp outside provider");
  return v;
}
