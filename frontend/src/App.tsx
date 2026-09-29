import { createContext, useContext, useEffect, useState } from "react";
import { api, setCsrf } from "./api";
import { Link, match, useRouter } from "./router";
import { Loading } from "./components";
import InitWizard from "./pages/InitWizard";
import Login from "./pages/Login";
import Dashboard from "./pages/Dashboard";
import Users from "./pages/Users";
import AuditLog from "./pages/AuditLog";
import About from "./pages/About";
import FiscalYears from "./pages/FiscalYears";
import FiscalYearDetail from "./pages/FiscalYearDetail";
import Budgets from "./pages/Budgets";
import BankAccounts from "./pages/BankAccounts";
import Register from "./pages/Register";
import Entities from "./pages/Entities";
import Account from "./pages/Account";
import Reports from "./pages/Reports";

export interface Me {
  id: number;
  username: string;
  email: string;
  security_domain: "ADMINISTRATOR" | "FINANCIAL" | "AUDITOR";
  roles: string[];
  permissions: string[];
  theme: "light" | "dark";
  csrf_token: string;
}

const MeCtx = createContext<{ me: Me; can: (p: string) => boolean; refresh: () => Promise<void>; setTheme: (t: "light" | "dark") => void } | null>(null);

export function useMe() {
  const c = useContext(MeCtx);
  if (!c) throw new Error("no user");
  return c;
}

function applyTheme(t: string) {
  document.documentElement.dataset.theme = t;
}

export default function App() {
  const [status, setStatus] = useState<any>(null);
  const [me, setMe] = useState<Me | null | undefined>(undefined);

  const loadMe = async () => {
    try {
      const m = await api.get<Me>("/api/auth/me");
      setCsrf(m.csrf_token);
      applyTheme(m.theme);
      setMe(m);
    } catch {
      setCsrf(null);
      applyTheme("light");
      setMe(null);
    }
  };

  const boot = async () => {
    const s = await api.get("/api/system/status");
    setStatus(s);
    if (s.initialized) await loadMe();
    else setMe(null);
  };

  useEffect(() => {
    boot();
    const on = () => {
      setCsrf(null);
      setMe(null);
    };
    window.addEventListener("fm:unauthenticated", on);
    return () => window.removeEventListener("fm:unauthenticated", on);
  }, []);

  if (!status || me === undefined) return <div className="center"><Loading /></div>;
  if (!status.initialized) return <InitWizard onDone={boot} />;
  if (!me) return <Login workspace={status.workspace_name} onLogin={loadMe} />;

  const ctx = {
    me,
    can: (p: string) => me.permissions.includes(p),
    refresh: loadMe,
    setTheme: (t: "light" | "dark") => {
      applyTheme(t);
      setMe({ ...me, theme: t });
    },
  };
  return (
    <MeCtx.Provider value={ctx}>
      <Shell workspace={status.workspace_name} warning={status.insecure_transport_warning} onLogout={() => { setCsrf(null); setMe(null); }} />
    </MeCtx.Provider>
  );
}

function navFor(me: Me) {
  const fin = [
    ["/", "Dashboard"],
    ["/fiscal-years", "Fiscal Years"],
    ["/budgets", "Budgets"],
    ["/bank-accounts", "Bank Accounts"],
    ["/register", "Register"],
    ["/entities", "Entities"],
    ["/reports", "Reports"],
  ];
  if (me.security_domain === "ADMINISTRATOR") return [["/", "Dashboard"], ["/users", "Users"], ["/audit-log", "Audit Log"], ["/about", "System/About"]];
  if (me.security_domain === "AUDITOR") return [...fin, ["/users", "Users"], ["/audit-log", "Audit Log"]];
  return fin;
}

function Shell({ workspace, warning, onLogout }: { workspace: string; warning: boolean; onLogout: () => void }) {
  const { me, can, setTheme } = useMe();
  const { path } = useRouter();
  const nav = navFor(me);
  const allowed = new Set(nav.map((n) => n[0]));
  const logout = async () => {
    try {
      await api.post("/api/auth/logout");
    } finally {
      onLogout();
    }
  };
  const toggleTheme = async () => {
    const t = me.theme === "dark" ? "light" : "dark";
    await api.put("/api/me/preferences", { theme: t });
    setTheme(t);
  };

  let page: JSX.Element;
  let m: Record<string, string> | null;
  const guard = (base: string, el: JSX.Element) => (allowed.has(base) ? el : <NotAuthorized />);
  if (path === "/") page = <Dashboard />;
  else if (path === "/account") page = <Account />;
  else if (path === "/users") page = guard("/users", <Users />);
  else if (path === "/audit-log") page = guard("/audit-log", <AuditLog />);
  else if (path === "/about") page = <About />;
  else if (path === "/fiscal-years") page = guard("/fiscal-years", <FiscalYears />);
  else if ((m = match("/fiscal-years/:id", path))) page = guard("/fiscal-years", <FiscalYearDetail id={Number(m.id)} />);
  else if (path === "/budgets") page = guard("/budgets", <Budgets />);
  else if (path === "/bank-accounts") page = guard("/bank-accounts", <BankAccounts />);
  else if (path === "/register") page = guard("/register", <Register />);
  else if (path === "/entities") page = guard("/entities", <Entities />);
  else if (path === "/reports") page = guard("/reports", <Reports />);
  else page = <p>Page not found.</p>;

  const roleNames: Record<string, string> = {
    ADMINISTRATOR: "Administrator", BUDGET_MANAGER: "Budget Manager", BUDGET_USER: "Budget User",
    REGISTER_USER: "Register User", AUDITOR: "Auditor",
  };
  return (
    <div className="shell">
      <header className="topbar">
        <div className="brand">
          <span className="logo" aria-hidden="true">◆</span> {workspace} <span className="muted">· Financial Management</span>
        </div>
        <div className="userbox">
          <span className="muted">{me.username} ({me.roles.map((r) => roleNames[r] || r).join(", ")})</span>
          <button className="small" onClick={toggleTheme} aria-label={`Switch to ${me.theme === "dark" ? "light" : "dark"} mode`}>
            {me.theme === "dark" ? "☀ Light" : "☾ Dark"}
          </button>
          <Link to="/account" className="small-link">My account</Link>
          <button className="small" onClick={logout}>Sign out</button>
        </div>
      </header>
      {warning ? <div className="alert warn banner" role="alert">Security warning: this server is exposed on a network without HTTPS configuration. Deploy behind an HTTPS reverse proxy.</div> : null}
      <div className="body">
        <nav className="sidenav" aria-label="Main navigation">
          {nav.map(([to, label]) => (
            <Link key={to} to={to}>{label}</Link>
          ))}
          {can("financial.view") ? null : null}
        </nav>
        <main className="content">{page}</main>
      </div>
    </div>
  );
}

function NotAuthorized() {
  return <div className="alert error" role="alert">You are not authorized to view this module.</div>;
}
