import { useEffect, useState } from "react";
import { api } from "../api";
import { BuildDetails, Loading } from "../components";
import { BackupRestore } from "./BackupRestore";

export default function About() {
  const [a, setA] = useState<any>(null);
  useEffect(() => {
    api.get("/api/system/about").then(setA);
  }, []);
  if (!a) return <Loading />;
  return (
    <div>
      <h1>System / About</h1>
      <BuildDetails info={a} />
      {a.bind_host ? <dl className="dl"><dt>Bind address</dt><dd>{a.bind_host}:{a.port}</dd></dl> : null}
      {a.insecure_transport_warning ? <div className="alert warn">Network deployment without HTTPS configuration is not secure.</div> : null}
      <div className="alert warn" role="note"><strong>Data protection:</strong> {a.backup_notice}</div>
      {a.restore_max_mb != null ? <BackupRestore maxMb={a.restore_max_mb} /> : null}
    </div>
  );
}
