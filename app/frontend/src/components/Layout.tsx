import { useState } from "react";
import { NavLink, Outlet } from "react-router-dom";
import { useApp } from "../state/AppContext";
import { LlmStatusPill } from "./LlmStatusPill";
import { login, logout, type RoleKey } from "../api/client";

const DEMO_ROLES: RoleKey[] = ["guest", "associate", "manager", "compliance"];

const LOGIN_ERRORS: Record<string, string> = {
  idp_denied: "The sign-in was cancelled or denied.",
  invalid_state: "The sign-in link expired. Please try again.",
};

function loginErrorMessage(): string | null {
  const code = new URLSearchParams(window.location.search).get("login_error");
  if (!code) return null;
  return LOGIN_ERRORS[code] ?? "The sign-in failed. Please try again.";
}

function LogoutButton() {
  const [error, setError] = useState<string | null>(null);
  return (
    <>
      <button
        type="button"
        className="secondary"
        onClick={() => {
          setError(null);
          logout().catch((e: unknown) => setError(e instanceof Error ? e.message : String(e)));
        }}
      >
        Sign out
      </button>
      {error && <span className="error">{error}</span>}
    </>
  );
}

function AuthPanel() {
  const { authStatus, authDetail } = useApp();
  if (authStatus === "loading") return <p>Checking your session…</p>;
  if (authStatus === "denied") {
    return (
      <section className="panel stack">
        <h2>No access</h2>
        <p>Your account has no platform role. Ask an administrator to assign one.</p>
        <div>
          <LogoutButton />
        </div>
      </section>
    );
  }
  if (authStatus === "unavailable") {
    return (
      <section className="panel stack">
        <h2>Sign-in is unavailable</h2>
        <p className="error">{authDetail}</p>
      </section>
    );
  }
  const loginError = loginErrorMessage();
  return (
    <section className="panel stack">
      <h2>Sign in</h2>
      <p>Sign in to ask questions. Your role decides which documents you can see.</p>
      {loginError && <p className="error">{loginError}</p>}
      <div>
        <button type="button" onClick={login}>
          Sign in
        </button>
      </div>
    </section>
  );
}

export function Layout() {
  const { authMode, authStatus, role, me, setRole } = useApp();
  const ready = authStatus === "ready";
  return (
    <div className="app-shell">
      <header className="brand-bar">
        <div className="brand">
          <strong>RetailPartnerX</strong>
          <span>Knowledge Platform · GraphRAG + Labels</span>
        </div>
        <div className="controls">
          {authMode === "demo" && (
            <label className="field" style={{ minWidth: 160 }}>
              Role (demo)
              <select value={role} onChange={(e) => setRole(e.target.value as RoleKey)}>
                {DEMO_ROLES.map((r) => (
                  <option key={r} value={r}>
                    {r}
                  </option>
                ))}
              </select>
            </label>
          )}
          {authMode === "oidc" && me && (
            <>
              <span data-testid="current-user">
                {me.username} · {me.role}
              </span>
              <LogoutButton />
            </>
          )}
          {ready && <LlmStatusPill />}
        </div>
      </header>
      {ready ? (
        <>
          <nav className="nav" style={{ marginBottom: "1.25rem" }}>
            {(
              [
                ["/", "Chat", true],
                ["/labels", "Labels", false],
                ["/llm", "LLM", false],
                ["/graph", "Graph", false],
                ["/ops", "Ops", false],
              ] as const
            ).map(([to, label, end]) => (
              <NavLink key={to} to={to} end={end} className={({ isActive }) => (isActive ? "active" : undefined)}>
                {label}
              </NavLink>
            ))}
          </nav>
          <Outlet />
        </>
      ) : (
        <AuthPanel />
      )}
    </div>
  );
}
