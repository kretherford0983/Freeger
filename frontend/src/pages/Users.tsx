import { useEffect, useState, type FormEvent } from "react";
import { api } from "../api";
import { ErrorBox, Field, Loading, Modal } from "../components";
import { useMe } from "../App";

const ROLES: Record<string, [string, string][]> = {
  ADMINISTRATOR: [["ADMINISTRATOR", "Administrator"]],
  FINANCIAL: [["BUDGET_MANAGER", "Budget Manager"], ["BUDGET_USER", "Budget User"], ["REGISTER_USER", "Register User"]],
  AUDITOR: [["AUDITOR", "Auditor"]],
};

export default function Users() {
  const { can } = useMe();
  const [users, setUsers] = useState<any[] | null>(null);
  const [edit, setEdit] = useState<any | null>(null);
  const [reset, setReset] = useState<any | null>(null);
  const [err, setErr] = useState<unknown>(null);
  const load = () => api.get("/api/users").then(setUsers, setErr);
  useEffect(() => {
    load();
  }, []);
  if (!users) return <><ErrorBox error={err} /><Loading /></>;
  const manage = can("users.manage");
  return (
    <div>
      <div className="page-head">
        <h1>Users</h1>
        {manage ? <button className="primary" onClick={() => setEdit({})}>New user</button> : null}
      </div>
      <ErrorBox error={err} />
      <table className="table">
        <thead><tr><th>Username</th><th>Email</th><th>Security domain</th><th>Roles</th><th>Status</th>{manage ? <th /> : null}</tr></thead>
        <tbody>
          {users.map((u) => (
            <tr key={u.id}>
              <td>{u.username}</td><td>{u.email}</td><td>{u.security_domain}</td><td>{u.roles.join(", ")}</td>
              <td>{u.active ? "Active" : "Disabled"}</td>
              {manage ? (
                <td className="actions-cell">
                  <button className="small" onClick={() => setEdit(u)}>Edit</button>
                  <button className="small" onClick={() => setReset(u)}>Reset password</button>
                </td>
              ) : null}
            </tr>
          ))}
        </tbody>
      </table>
      {edit ? <UserForm user={edit} onClose={() => setEdit(null)} onSaved={() => { setEdit(null); load(); }} /> : null}
      {reset ? <ResetForm user={reset} onClose={() => setReset(null)} /> : null}
    </div>
  );
}

function UserForm({ user, onClose, onSaved }: { user: any; onClose: () => void; onSaved: () => void }) {
  const isNew = !user.id;
  const [f, setF] = useState({
    username: user.username || "", email: user.email || "", display_name: user.display_name || "", password: "",
    security_domain: user.security_domain || "FINANCIAL", roles: (user.roles || []) as string[], active: user.active ?? true,
  });
  const [err, setErr] = useState<unknown>(null);
  const toggle = (r: string) => setF({ ...f, roles: f.roles.includes(r) ? f.roles.filter((x) => x !== r) : [...f.roles, r] });
  const setDomain = (d: string) => setF({ ...f, security_domain: d, roles: d === "FINANCIAL" ? [] : [ROLES[d][0][0]] });
  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setErr(null);
    try {
      if (isNew) {
        await api.post("/api/users", { username: f.username, email: f.email, display_name: f.display_name || null, password: f.password,
          security_domain: f.security_domain, roles: f.roles });
      } else {
        await api.patch(`/api/users/${user.id}`, { email: f.email, display_name: f.display_name || null,
          security_domain: f.security_domain, roles: f.roles, active: f.active });
      }
      onSaved();
    } catch (x) {
      setErr(x);
    }
  };
  return (
    <Modal title={isNew ? "New user" : `Edit ${user.username}`} onClose={onClose}>
      <form onSubmit={submit}>
        <ErrorBox error={err} />
        {isNew ? <Field label="Username"><input required value={f.username} onChange={(e) => setF({ ...f, username: e.target.value })} /></Field> : null}
        <Field label="Email"><input required type="email" value={f.email} onChange={(e) => setF({ ...f, email: e.target.value })} /></Field>
        <Field label="Display name"><input value={f.display_name} onChange={(e) => setF({ ...f, display_name: e.target.value })} /></Field>
        {isNew ? <Field label="Initial password" hint="At least 12 characters including a letter and a digit."><input required type="password" autoComplete="new-password" value={f.password} onChange={(e) => setF({ ...f, password: e.target.value })} /></Field> : null}
        <fieldset>
          <legend>Security domain (exactly one)</legend>
          {Object.keys(ROLES).map((d) => (
            <label key={d} className="check"><input type="radio" name="domain" checked={f.security_domain === d} onChange={() => setDomain(d)} /> {d}</label>
          ))}
        </fieldset>
        {f.security_domain === "FINANCIAL" ? (
          <fieldset>
            <legend>Financial roles</legend>
            {ROLES.FINANCIAL.map(([code, name]) => (
              <label key={code} className="check"><input type="checkbox" checked={f.roles.includes(code)} onChange={() => toggle(code)} /> {name}</label>
            ))}
          </fieldset>
        ) : null}
        {!isNew ? <label className="check"><input type="checkbox" checked={f.active} onChange={(e) => setF({ ...f, active: e.target.checked })} /> Active</label> : null}
        <div className="actions"><button type="button" onClick={onClose}>Cancel</button><button className="primary" type="submit">Save</button></div>
      </form>
    </Modal>
  );
}

function ResetForm({ user, onClose }: { user: any; onClose: () => void }) {
  const [pw, setPw] = useState("");
  const [err, setErr] = useState<unknown>(null);
  const [done, setDone] = useState(false);
  const submit = async (e: FormEvent) => {
    e.preventDefault();
    try {
      await api.post(`/api/users/${user.id}/reset-password`, { new_password: pw });
      setDone(true);
    } catch (x) {
      setErr(x);
    }
  };
  return (
    <Modal title={`Reset password for ${user.username}`} onClose={onClose}>
      <form onSubmit={submit}>
        <ErrorBox error={err} />
        {done ? <div className="alert ok">Password reset. The user's sessions were signed out.</div> : (
          <>
            <Field label="New password"><input type="password" required autoComplete="new-password" value={pw} onChange={(e) => setPw(e.target.value)} /></Field>
            <div className="actions"><button type="button" onClick={onClose}>Cancel</button><button className="primary" type="submit">Reset</button></div>
          </>
        )}
      </form>
    </Modal>
  );
}
