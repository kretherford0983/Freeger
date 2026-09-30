import { lazy, Suspense, useEffect, useState } from "react";
import { api, money } from "../api";
import { ErrorBox, FyStatus, Loading, Remaining } from "../components";
import { Link } from "../router";
import { useMe } from "../App";
const DashboardCharts = lazy(() => import("./Charts")); // v1.4.1 CR-020: chart library loaded on demand

export default function Dashboard() {
  const { me } = useMe();
  const [d, setD] = useState<any>(null);
  const [err, setErr] = useState<unknown>(null);
  useEffect(() => {
    api.get("/api/dashboard").then(setD, setErr);
  }, []);
  if (err) return <ErrorBox error={err} />;
  if (!d) return <Loading />;
  if (d.kind === "administrator")
    return (
      <div>
        <h1>Administration</h1>
        <div className="tiles">
          <div className="tile"><div className="tile-label">Users</div><div className="tile-value">{d.user_count}</div></div>
          <div className="tile"><div className="tile-label">Active users</div><div className="tile-value">{d.active_user_count}</div></div>
          <div className="tile"><div className="tile-label">Failed sign-ins (24h)</div><div className="tile-value">{d.failed_logins_24h}</div></div>
        </div>
        <h2>Active users by security domain</h2>
        <ul>{Object.entries(d.active_users_by_domain).map(([k, v]) => <li key={k}>{k}: {String(v)}</li>)}</ul>
        <p><Link to="/users">Manage users</Link> · <Link to="/audit-log">View audit log</Link></p>
      </div>
    );
  const fy = d.current_fiscal_year;
  return (
    <div>
      <h1>{me.security_domain === "AUDITOR" ? "Auditor dashboard" : "Dashboard"}</h1>
      <section className="card">
        <h2>Current Fiscal Year</h2>
        {fy ? (
          <p><Link to={`/fiscal-years/${fy.id}`}>{fy.display_name}</Link> <FyStatus status={fy.status} /> {fy.start_date} – {fy.end_date}</p>
        ) : (
          <p className="muted">No Fiscal Year configured.</p>
        )}
        {d.fiscal_years?.length ? (
          <p className="muted">All Fiscal Years: {d.fiscal_years.map((f: any) => f.label).join(" · ")}</p>
        ) : null}
      </section>
      {d.budget_summary ? (
        <div className="tiles">
          {(["income", "expense"] as const).map((k) => (
            <div className="tile" key={k}>
              <div className="tile-label">{k === "income" ? "Income" : "Expense"} budget</div>
              <div className="tile-value">{money(d.budget_summary[k].amount)}</div>
              <div className="muted">Actual {money(d.budget_summary[k].actual)} · Remaining <Remaining x={d.budget_summary[k]} /></div>
            </div>
          ))}
        </div>
      ) : null}
      {d.review_summary ? (
        <section className="card">
          <h2>Review summary</h2>
          <div className="tiles">
            <Tile label="Transactions" v={d.review_summary.transaction_count} />
            <Tile label="Voided transactions" v={d.review_summary.voided_transaction_count} />
            <Tile label="Cross-FY allocations" v={d.review_summary.cross_fiscal_year_allocation_count} />
            <Tile label="Pending FY reviews" v={d.review_summary.pending_fiscal_year_reviews} />
            <Tile label="Rejected budgets with activity" v={d.review_summary.rejected_budgets_with_activity} />
          </div>
        </section>
      ) : null}
      <section className="card">
        <h2>Bank account balances</h2>
        <table className="table">
          <thead><tr><th>Account</th><th className="num">Current balance</th></tr></thead>
          <tbody>
            {d.bank_accounts.map((a: any) => (
              <tr key={a.id}><td>{a.label} {a.is_primary ? <span className="pill">Primary</span> : null}</td><td className="num">{money(a.current_balance)}</td></tr>
            ))}
          </tbody>
          {d.bank_accounts.length ? (
            <tfoot><tr className="total-row" data-testid="bank-total"><th scope="row">Total (all accounts)</th><th className={`num ${Number(d.bank_accounts_total) < 0 ? "neg" : ""}`}>{money(d.bank_accounts_total)}</th></tr></tfoot>
          ) : null}
        </table>
      </section>
      <section className="card">
        <h2>Attention</h2>
        <ul>
          <li>Fiscal Year review items pending: <b>{d.attention.pending_fiscal_year_reviews}</b> {d.attention.pending_fiscal_year_reviews ? <Link to="/register?reviews=1">Review</Link> : null}</li>
          <li>Uncleared transactions: <b>{d.attention.uncleared_transactions}</b></li>
          {fy ? <li>Documentation review warnings ({fy.display_name}): <b>{d.attention.documentation_warnings}</b> {d.attention.documentation_warnings ? <Link to={`/fiscal-years/${fy.id}`}>Review</Link> : null}</li> : null}
        </ul>
      </section>
      <Suspense fallback={<section className="card"><h2>Charts</h2><p className="hint">Loading charts…</p></section>}>
        <DashboardCharts fys={d.fiscal_years || []} currentFyId={fy ? fy.id : null} />
      </Suspense>
    </div>
  );
}

function Tile({ label, v }: { label: string; v: any }) {
  return <div className="tile"><div className="tile-label">{label}</div><div className="tile-value">{v}</div></div>;
}
