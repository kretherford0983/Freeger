// Same-origin API client. Authentication is an HttpOnly server-side session cookie; the CSRF token is kept
// only in memory (never in localStorage/sessionStorage) and sent as X-CSRF-Token on state-changing requests.

let csrfToken: string | null = null;

export function setCsrf(token: string | null) {
  csrfToken = token;
}

export interface ApiWarning {
  code: string;
  message: string;
  details: Record<string, unknown>;
}

export class ApiError extends Error {
  status: number;
  code: string;
  body: any;
  constructor(status: number, body: any) {
    super(body?.error?.message || `Request failed (${status})`);
    this.status = status;
    this.code = body?.error?.code || "ERROR";
    this.body = body?.error || {};
  }
  get warnings(): ApiWarning[] {
    return this.body?.warnings || [];
  }
  get fieldErrors(): { field: string | null; message: string }[] {
    return this.body?.errors || [];
  }
}

async function request<T>(method: string, url: string, body?: unknown, isForm = false): Promise<T> {
  const headers: Record<string, string> = { Accept: "application/json" };
  if (method !== "GET" && csrfToken) headers["X-CSRF-Token"] = csrfToken;
  let payload: BodyInit | undefined;
  if (body !== undefined) {
    if (isForm) payload = body as FormData;
    else {
      headers["Content-Type"] = "application/json";
      payload = JSON.stringify(body);
    }
  }
  const res = await fetch(url, { method, headers, body: payload, credentials: "same-origin" });
  const text = await res.text();
  let data: any = null;
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    data = null;
  }
  if (!res.ok) {
    const err = new ApiError(res.status, data);
    if (res.status === 401 && !url.startsWith("/api/auth/login")) {
      window.dispatchEvent(new CustomEvent("fm:unauthenticated"));
    }
    throw err;
  }
  return data as T;
}

export const api = {
  get: <T = any>(url: string) => request<T>("GET", url),
  post: <T = any>(url: string, body?: unknown) => request<T>("POST", url, body ?? {}),
  patch: <T = any>(url: string, body?: unknown) => request<T>("PATCH", url, body ?? {}),
  put: <T = any>(url: string, body?: unknown) => request<T>("PUT", url, body ?? {}),
  delete: <T = any>(url: string) => request<T>("DELETE", url),
  upload: <T = any>(url: string, file: File) => {
    const fd = new FormData();
    fd.append("file", file);
    return request<T>("POST", url, fd, true);
  },
};

export async function preAuthCsrf() {
  const r = await api.get<{ csrf_token: string }>("/api/auth/csrf");
  setCsrf(r.csrf_token);
}

export function qs(params: Record<string, string | number | boolean | null | undefined>) {
  const p = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => {
    if (v !== null && v !== undefined && v !== "") p.set(k, String(v));
  });
  const s = p.toString();
  return s ? `?${s}` : "";
}

export function money(v: string | null | undefined) {
  if (v === null || v === undefined) return "";
  const n = Number(v);
  const neg = n < 0;
  const [i, d] = Math.abs(n).toFixed(2).split(".");
  return `${neg ? "-" : ""}$${i.replace(/\B(?=(\d{3})+(?!\d))/g, ",")}.${d}`;
}

export function todayIso() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

/** v1.3 CR-011: one-time key for a create form (works on plain-HTTP LAN addresses, unlike crypto.randomUUID). */
export function newRequestKey() {
  const b = new Uint8Array(16);
  crypto.getRandomValues(b);
  return Array.from(b, (x) => x.toString(16).padStart(2, "0")).join("");
}
