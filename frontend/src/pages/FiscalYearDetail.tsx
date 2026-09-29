import { useEffect, useState } from "react";
import { api } from "../api";
import { Attachments, ErrorBox, FyStatus, Loading, Modal } from "../components";
import { useMe } from "../App";
import { Link } from "../router";
import { BudgetSection } from "./BudgetTable";

export default function FiscalYearDetail({ id }: { id: number }) {
  const { can } = useMe();
  const [d, setD] = useState<any>(null);
  const [err, setErr] = useState<unknown>(null);
  const [dlg, setDlg] = useState<"approve" | "close" | null>(null);
  const load = () => api.get(`/api/fiscal-years/${id}`).then(setD, setErr);
  useEffect(() => {
    setD(null);
    load();
  }, [id]);
  if (!d) return <><ErrorBox error={err} />{err ? null : <Loading />}</>;
  const manage = can("fiscal_year.manage");
  const b = d.budgets;
  const showOutside = [...b.income, ...b.expense].some((r: any) => Number(r.outside_fiscal_year) !== 0);
  return (
    <div>
      <p><Link to="/fiscal-years">← Fiscal Years</Link></p>
      <div className="page-head">
        <h1>{d.display_name} <FyStatus status={d.status} /></h1>
        {manage && d.status === "DRAFT" ? <button className="primary" onClick={() => setDlg("approve")}>Approve…</button> : null}
        {manage && d.status === "APPROVED" ? <button className="primary" onClick={() => setDlg("close")}>Close Fiscal Year…</button> : null}
        {can("budget.manage") && d.status !== "CLOSED" ? <Link to={`/budgets?fiscal_year_id=${d.id}`}>Edit budgets</Link> : null}
      </div>
      <ErrorBox error={err} />
      <dl className="dl">
        <dt>Dates</dt><dd>{d.start_date} – {d.end_date}</dd>
        <dt>Quarters</dt><dd>{b.quarters.map((q: any) => `${q.name}: ${q.start_date} – ${q.end_date}`).join(" · ")}</dd>
        <dt>Created</dt><dd>{d.created_at?.replace("T", " ").slice(0, 16)}</dd>
        <dt>Approved</dt><dd>{d.approved_at ? d.approved_at.replace("T", " ").slice(0, 16) : "—"}</dd>
        <dt>Closed</dt><dd>{d.closed_at ? d.closed_at.replace("T", " ").slice(0, 16) : "—"}</dd>
        {d.exception_confirmed ? <><dt>Confirmed exceptions</dt><dd>{d.exception_confirmed}</dd></> : null}
      </dl>
      <BudgetSection title="Income" rows={b.income} summary={b.income_summary} fyStatus="CLOSED" showOutside={showOutside} />
      <BudgetSection title="Expense" rows={b.expense} summary={b.expense_summary} fyStatus="CLOSED" showOutside={showOutside} />
      {d.status !== "CLOSED" ? <Closure c={d.closure} /> : null}
      <Attachments ownerType="fiscal_year" ownerId={d.id} canUpload={manage} canRemove={manage && d.status !== "CLOSED"} title="Supporting documentation" />
      {dlg === "approve" ? <Approve fy={d} onClose={() => setDlg(null)} onDone={() => { setDlg(null); load(); }} /> : null}
      {dlg === "close" ? <Close fy={d} onClose={() => setDlg(null)} onDone={() => { setDlg(null); load(); }} /> : null}
    </div>
  );
}

function Closure({ c }: { c: any }) {
  return (
    <section className="card">
      <h3>Closure readiness</h3>
      {c.blockers.length ? (
        <ul className="blockers">{c.blockers.map((b: any) => <li key={b.code}><span className="badge red">Blocker</span> {b.message}</li>)}</ul>
      ) : <p className="ok-text">No closure blockers.</p>}
      {c.warnings.length ? <ul>{c.warnings.map((w: any) => <li key={w.code}><span className="badge yellow">Warning</span> {w.message}</li>)}</ul> : null}
    </section>
  );
}

function Approve({ fy, onClose, onDone }: any) {
  const [ok, setOk] = useState(false);
  const [err, setErr] = useState<unknown>(null);
  const go = async () => {
    try { await api.post(`/api/fiscal-years/${fy.id}/approve`, { confirm_irreversible: true }); onDone(); } catch (e) { setErr(e); }
  };
  return (
    <Modal title={`Approve ${fy.display_name}`} onClose={onClose}>
      <ErrorBox error={err} />
      <div className="alert warn">Approval is irreversible and locks all active budgets. Amendments later require an explicit, audited unlock.</div>
      <label className="check"><input type="checkbox" checked={ok} onChange={(e) => setOk(e.target.checked)} /> I understand approval cannot be reversed.</label>
      <div className="actions"><button onClick={onClose}>Cancel</button><button className="primary" disabled={!ok} onClick={go}>Approve</button></div>
    </Modal>
  );
}

function Close({ fy, onClose, onDone }: any) {
  const [ok, setOk] = useState(false);
  const [err, setErr] = useState<unknown>(null);
  const go = async () => {
    try { await api.post(`/api/fiscal-years/${fy.id}/close`, { confirm_reviewed: true }); onDone(); } catch (e) { setErr(e); }
  };
  return (
    <Modal title={`Close ${fy.display_name}`} onClose={onClose}>
      <ErrorBox error={err} />
      <Closure c={fy.closure} />
      <div className="alert warn">Closure is irreversible. Budgets and allocations of a Closed Fiscal Year become immutable.</div>
      <label className="check"><input type="checkbox" checked={ok} onChange={(e) => setOk(e.target.checked)} /> I confirm this Fiscal Year has been reviewed and is approved for closure.</label>
      <div className="actions"><button onClick={onClose}>Cancel</button><button className="primary danger" disabled={!ok || !fy.closure.can_close} onClick={go}>Close Fiscal Year</button></div>
    </Modal>
  );
}
