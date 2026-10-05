import { NavLink, Outlet } from "react-router-dom";
import { useApp } from "../state/AppContext";
import { LlmStatusPill } from "./LlmStatusPill";
import type { RoleKey } from "../api/client";

const ROLES: RoleKey[] = ["guest", "associate", "manager", "compliance"];

export function Layout() {
  const { role, setRole } = useApp();
  return (
    <div className="app-shell">
      <header className="brand-bar">
        <div className="brand">
          <strong>RetailPartnerX</strong>
          <span>Knowledge Platform · GraphRAG + Labels</span>
        </div>
        <div className="controls">
          <label className="field" style={{ minWidth: 160 }}>
            Role
            <select value={role} onChange={(e) => setRole(e.target.value as RoleKey)}>
              {ROLES.map((r) => (
                <option key={r} value={r}>
                  {r}
                </option>
              ))}
            </select>
          </label>
          <LlmStatusPill />
        </div>
      </header>
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
    </div>
  );
}
