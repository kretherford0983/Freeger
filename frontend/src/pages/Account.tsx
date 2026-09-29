import { useState, type FormEvent } from "react";
import { api } from "../api";
import { ErrorBox, Field } from "../components";
import { useMe } from "../App";

export default function Account() {
  const { me, setTheme } = useMe();
  const [f, setF] = useState({ current_password: "", new_password: "", new_password_confirmation: "" });
  const [err, setErr] = useState<unknown>(null);
  const [ok, setOk] = useState(false);
  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setErr(null);
    setOk(false);
    try {
      await api.post("/api/auth/change-password", f);
      setF({ current_password: "", new_password: "", new_password_confirmation: "" });
      setOk(true);
    } catch (x) {
      setErr(x);
    }
  };
  const theme = async (t: "light" | "dark") => {
    await api.put("/api/me/preferences", { theme: t });
    setTheme(t);
  };
  return (
    <div>
      <h1>My account</h1>
      <p>Signed in as <b>{me.username}</b> ({me.email})</p>
      <section className="card">
        <h2>Appearance</h2>
        <div role="radiogroup" aria-label="Theme" className="row">
          <label className="check"><input type="radio" name="theme" checked={me.theme === "light"} onChange={() => theme("light")} /> Light</label>
          <label className="check"><input type="radio" name="theme" checked={me.theme === "dark"} onChange={() => theme("dark")} /> Dark</label>
        </div>
        <p className="hint">Your preference is saved to your account and applies on every sign-in.</p>
      </section>
      <form className="card" onSubmit={submit}>
        <h2>Change password</h2>
        <ErrorBox error={err} />
        {ok ? <div className="alert ok" role="status">Password changed. Your other sessions were signed out.</div> : null}
        <Field label="Current password"><input type="password" required autoComplete="current-password" value={f.current_password} onChange={(e) => setF({ ...f, current_password: e.target.value })} /></Field>
        <Field label="New password" hint="At least 12 characters including a letter and a digit."><input type="password" required autoComplete="new-password" value={f.new_password} onChange={(e) => setF({ ...f, new_password: e.target.value })} /></Field>
        <Field label="Confirm new password"><input type="password" required autoComplete="new-password" value={f.new_password_confirmation} onChange={(e) => setF({ ...f, new_password_confirmation: e.target.value })} /></Field>
        <button className="primary" type="submit">Change password</button>
      </form>
    </div>
  );
}
