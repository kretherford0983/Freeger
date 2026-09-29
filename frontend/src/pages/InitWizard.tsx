import { useEffect, useState, type FormEvent } from "react";
import { api, preAuthCsrf } from "../api";
import { ErrorBox, Field } from "../components";

export default function InitWizard({ onDone }: { onDone: () => void }) {
  const [f, setF] = useState({ workspace_name: "", admin_username: "", admin_email: "", password: "", password_confirmation: "" });
  const [err, setErr] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    preAuthCsrf();
  }, []);
  const set = (k: keyof typeof f) => (e: any) => setF({ ...f, [k]: e.target.value });
  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setErr(null);
    if (f.password !== f.password_confirmation) {
      setErr(new Error("Password and confirmation do not match."));
      return;
    }
    setBusy(true);
    try {
      await api.post("/api/system/initialize", f);
      onDone();
    } catch (x) {
      setErr(x);
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="center">
      <form className="card auth-card" onSubmit={submit} aria-labelledby="init-title">
        <h1 id="init-title">Initialization Wizard</h1>
        <p className="muted">This installation has not been initialized. Create the Workspace and the initial Administrator. No default credentials exist.</p>
        <ErrorBox error={err} />
        <Field label="Organization / Workspace Name"><input required maxLength={120} value={f.workspace_name} onChange={set("workspace_name")} /></Field>
        <Field label="Administrator Username"><input required minLength={3} maxLength={64} autoComplete="username" value={f.admin_username} onChange={set("admin_username")} /></Field>
        <Field label="Administrator Email Address"><input required type="email" maxLength={254} value={f.admin_email} onChange={set("admin_email")} /></Field>
        <Field label="Password" hint="At least 12 characters including a letter and a digit.">
          <input required type="password" minLength={12} autoComplete="new-password" value={f.password} onChange={set("password")} />
        </Field>
        <Field label="Password Confirmation"><input required type="password" autoComplete="new-password" value={f.password_confirmation} onChange={set("password_confirmation")} /></Field>
        <p className="hint">The POC does not provide backup/restore. Protect the application data directory (database, attachments and secrets) yourself.</p>
        <button className="primary" disabled={busy} type="submit">Initialize</button>
      </form>
    </div>
  );
}
