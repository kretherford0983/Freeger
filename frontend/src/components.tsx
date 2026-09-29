import { useEffect, useRef, useState, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { api, ApiError, type ApiWarning, qs } from "./api";

export function Modal({ title, onClose, children, wide }: { title: string; onClose: () => void; children: ReactNode; wide?: boolean }) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    ref.current?.focus();
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);
  // Portal: nested dialogs (e.g. "new institution" inside the account form) must not nest <form> elements.
  return createPortal(
    <div className="modal-backdrop" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className={`modal${wide ? " wide" : ""}`} role="dialog" aria-modal="true" aria-label={title} tabIndex={-1} ref={ref}>
        <div className="modal-head">
          <h2>{title}</h2>
          <button className="icon-btn" onClick={onClose} aria-label="Close">×</button>
        </div>
        <div className="modal-body">{children}</div>
      </div>
    </div>,
    document.body,
  );
}

export function ErrorBox({ error }: { error: unknown }) {
  if (!error) return null;
  const e = error as ApiError;
  const msg = e?.message || String(error);
  return (
    <div className="alert error" role="alert">
      <strong>{msg}</strong>
      {e?.fieldErrors?.length ? (
        <ul>
          {e.fieldErrors.map((f, i) => (
            <li key={i}>
              {f.field ? <code>{f.field}</code> : null} {f.message}
            </li>
          ))}
        </ul>
      ) : null}
      {e?.body?.blockers?.length ? (
        <ul>
          {e.body.blockers.map((b: any) => (
            <li key={b.code}>{b.message}</li>
          ))}
        </ul>
      ) : null}
      {e?.body?.candidates?.length ? (
        <p>Candidates: {e.body.candidates.map((c: any) => c.label).join(", ")}</p>
      ) : null}
    </div>
  );
}

function WarningDetails({ w }: { w: ApiWarning }) {
  const d: any = w.details || {};
  return (
    <div className="warning-details">
      {d.gaps?.map((g: any, i: number) => (
        <p key={i}>
          Uncovered dates: <b>{g.from}</b> to <b>{g.to}</b> (adjacent {g.adjacent?.label})
        </p>
      ))}
      {d.overlapping?.map((o: any) => (
        <div key={o.id}>
          <p>
            Overlaps <b>{o.label}</b> ({o.start_date} – {o.end_date}).
          </p>
          <p className="muted">
            Closure readiness: {o.readiness?.can_close ? "ready to close" : (o.readiness?.blockers || []).map((b: any) => b.message).join("; ")}
          </p>
        </div>
      ))}
      {d.matches?.length ? (
        <table className="table compact">
          <thead>
            <tr><th>Entity #</th><th>Name</th><th>Type</th><th>Status</th><th>Email</th></tr>
          </thead>
          <tbody>
            {d.matches.map((m: any) => (
              <tr key={m.id}>
                <td>{m.entity_number}</td><td>{m.display_name}</td><td>{m.entity_type}</td>
                <td>{m.active ? "Active" : "Inactive"}</td><td>{m.email}</td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : null}
      {d.closest_fiscal_year ? <p>Closest configured Fiscal Year (reference only): <b>{d.closest_fiscal_year.label}</b></p> : null}
      {d.budget_fiscal_year && !d.closest_fiscal_year ? (
        <p>
          Budget Fiscal Year: <b>{d.budget_fiscal_year.label}</b>; natural Fiscal Year: {(d.natural_fiscal_years || []).map((f: any) => f.label).join(", ")}
        </p>
      ) : null}
    </div>
  );
}

/** Runs an action; if the server requires explicit confirmation, shows the warnings and re-submits with
 * the acknowledged codes. Confirmation is a blocking dialog with an explicit checkbox. */
export function useConfirmable() {
  const [pending, setPending] = useState<null | { warnings: ApiWarning[]; retry: (codes: string[]) => void; cancel: () => void }>(null);
  const [ack, setAck] = useState(false);
  async function run<T>(fn: (confirmations: string[]) => Promise<T>, acc: string[] = []): Promise<T | undefined> {
    try {
      return await fn(acc);
    } catch (e) {
      if (e instanceof ApiError && e.code === "CONFIRMATION_REQUIRED" && e.warnings.length) {
        return new Promise<T | undefined>((resolve, reject) => {
          setAck(false);
          setPending({
            warnings: e.warnings,
            retry: (codes) => {
              setPending(null);
              run(fn, [...acc, ...codes]).then(resolve, reject);
            },
            cancel: () => {
              setPending(null);
              resolve(undefined);
            },
          });
        });
      }
      throw e;
    }
  }
  const dialog = pending ? (
    <Modal title="Confirmation required" onClose={pending.cancel}>
      {pending.warnings.map((w) => (
        <div key={w.code} className="alert warn" role="alert">
          <strong>{w.message}</strong>
          <WarningDetails w={w} />
        </div>
      ))}
      <label className="check">
        <input type="checkbox" checked={ack} onChange={(e) => setAck(e.target.checked)} /> I have reviewed these warnings and explicitly confirm.
      </label>
      <div className="actions">
        <button onClick={pending.cancel}>Cancel</button>
        <button className="primary" disabled={!ack} onClick={() => pending.retry(pending.warnings.map((w) => w.code))}>
          Confirm and continue
        </button>
      </div>
    </Modal>
  ) : null;
  return { run, dialog };
}

export function Lock({ open }: { open: boolean }) {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" aria-hidden="true" className="lock-icon">
      <rect x="4" y="11" width="16" height="10" rx="2" fill="currentColor" />
      {open ? (
        <path d="M8 11V7a4 4 0 0 1 7.5-2" stroke="currentColor" strokeWidth="2.2" fill="none" />
      ) : (
        <path d="M8 11V7a4 4 0 0 1 8 0v4" stroke="currentColor" strokeWidth="2.2" fill="none" />
      )}
    </svg>
  );
}

export function BudgetState({ state }: { state: { code: string; icon: string; label: string } }) {
  const icon =
    state.icon === "lock-closed" ? <Lock open={false} /> : state.icon === "lock-open" ? <Lock open /> : <span className="glyph">{state.icon}</span>;
  return (
    <span className={`state state-${state.code.toLowerCase()}`} title={state.label}>
      <span role="img" aria-label={state.label}>{icon}</span> <span className="state-text">{state.label}</span>
    </span>
  );
}

export function FyStatus({ status }: { status: string }) {
  return <span className={`pill pill-${status.toLowerCase()}`}>{status.charAt(0) + status.slice(1).toLowerCase()}</span>;
}

export function Field({ label, children, hint }: { label: string; children: ReactNode; hint?: string }) {
  return (
    <div className="field">
      <label className="field-inner">
        <span className="field-label">{label}</span>
        {children}
      </label>
      {hint ? <span className="hint">{hint}</span> : null}
    </div>
  );
}

export function Loading() {
  return <p className="muted" aria-live="polite">Loading…</p>;
}

// ------------------------------------------------------------------ attachments
export function Attachments({ ownerType, ownerId, canUpload, canRemove, title = "Attachments" }: {
  ownerType: "fiscal_year" | "transaction" | "allocation";
  ownerId: number;
  canUpload: boolean;
  canRemove: boolean;
  title?: string;
}) {
  const [items, setItems] = useState<any[]>([]);
  const [err, setErr] = useState<unknown>(null);
  const [viewIdx, setViewIdx] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);
  const load = () => api.get(`/api/attachments${qs({ owner_type: ownerType, owner_id: ownerId })}`).then(setItems, setErr);
  useEffect(() => {
    load();
  }, [ownerType, ownerId]);
  const onFile = async (f: File | undefined) => {
    if (!f) return;
    setErr(null);
    if (f.size > 5 * 1024 * 1024) {
      setErr(new Error("Attachments may not exceed 5 MB per file."));
      return;
    }
    setBusy(true);
    try {
      await api.upload(`/api/attachments${qs({ owner_type: ownerType, owner_id: ownerId })}`, f);
      await load();
    } catch (e) {
      setErr(e);
    } finally {
      setBusy(false);
    }
  };
  const remove = async (id: number) => {
    if (!window.confirm("Remove this attachment? It is retained in history.")) return;
    try {
      await api.post(`/api/attachments/${id}/remove`);
      load();
    } catch (e) {
      setErr(e);
    }
  };
  const cur = viewIdx !== null ? items[viewIdx] : null;
  return (
    <section className="attachments">
      <h3>{title} ({items.length})</h3>
      <ErrorBox error={err} />
      {items.length ? (
        <ul className="att-list">
          {items.map((a, i) => (
            <li key={a.id}>
              <button className="link" onClick={() => setViewIdx(i)}>{a.original_filename}</button>{" "}
              <span className="muted">{a.mime_type} · {(a.size_bytes / 1024).toFixed(1)} KB</span>{" "}
              <a href={`${a.content_url}?download=true`}>Download</a>
              {canRemove ? <button className="small danger" onClick={() => remove(a.id)}>Remove</button> : null}
            </li>
          ))}
        </ul>
      ) : (
        <p className="muted">No attachments.</p>
      )}
      {canUpload ? (
        <label className="upload">
          <span>Add attachment (PDF, JPG, PNG; max 5 MB)</span>
          <input type="file" accept=".pdf,.jpg,.jpeg,.png,application/pdf,image/jpeg,image/png" disabled={busy}
                 onChange={(e) => { onFile(e.target.files?.[0]); e.target.value = ""; }} />
        </label>
      ) : null}
      {cur ? (
        <Modal title={`${cur.original_filename} (${(viewIdx ?? 0) + 1} of ${items.length})`} onClose={() => setViewIdx(null)} wide>
          <div className="viewer-nav">
            <button disabled={viewIdx === 0} onClick={() => setViewIdx((viewIdx ?? 0) - 1)}>◀ Previous</button>
            <span>{(viewIdx ?? 0) + 1} / {items.length}</span>
            <button disabled={viewIdx === items.length - 1} onClick={() => setViewIdx((viewIdx ?? 0) + 1)}>Next ▶</button>
          </div>
          {cur.mime_type === "application/pdf" ? (
            <iframe className="viewer" src={cur.content_url} title={cur.original_filename} />
          ) : (
            <img className="viewer-img" src={cur.content_url} alt={cur.original_filename} />
          )}
        </Modal>
      ) : null}
    </section>
  );
}
