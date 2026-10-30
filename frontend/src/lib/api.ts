export const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export type User = { id: number; email: string; name: string; company: string; role: string; model?: string };

export const auth = {
  get token() { return typeof window === "undefined" ? null : localStorage.getItem("erp_token"); },
  set(token: string) { localStorage.setItem("erp_token", token); },
  clear() { localStorage.removeItem("erp_token"); },
};

export async function api<T = any>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await fetch(`${API}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(auth.token ? { Authorization: `Bearer ${auth.token}` } : {}), ...(init.headers || {}) },
  });
  if (res.status === 401) {
    auth.clear();
    if (typeof window !== "undefined" && !location.pathname.startsWith("/login")) location.href = "/login";
  }
  if (!res.ok) {
    let msg = res.statusText;
    try { msg = (await res.json()).detail || msg; } catch {}
    throw new Error(msg);
  }
  return res.json();
}

/** POST that yields parsed SSE `data:` JSON events. */
export async function* streamSSE(path: string, body: unknown, signal?: AbortSignal): AsyncGenerator<any> {
  const res = await fetch(`${API}${path}`, {
    method: "POST", signal,
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${auth.token}` },
    body: JSON.stringify(body),
  });
  if (!res.ok || !res.body) throw new Error(`Request failed (${res.status})`);
  const reader = res.body.getReader();
  const dec = new TextDecoder();
  let buf = "";
  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buf += dec.decode(value, { stream: true });
    let i;
    while ((i = buf.indexOf("\n\n")) >= 0) {
      const chunk = buf.slice(0, i);
      buf = buf.slice(i + 2);
      for (const line of chunk.split("\n")) {
        if (line.startsWith("data:")) {
          try { yield JSON.parse(line.slice(5).trim()); } catch {}
        }
      }
    }
  }
}

export const fmt = {
  money: (n: number) => (n == null || isNaN(+n) ? "—" : `$${(+n).toLocaleString(undefined, { maximumFractionDigits: Math.abs(+n) >= 1000 ? 0 : 2 })}`),
  compact: (n: number) => (Math.abs(n) >= 1e6 ? `${(n / 1e6).toFixed(1)}M` : Math.abs(n) >= 1e3 ? `${(n / 1e3).toFixed(1)}K` : `${Math.round(n)}`),
  num: (n: number) => (n == null ? "—" : (+n).toLocaleString()),
  pct: (n: number) => `${(+n).toFixed(1)}%`,
  date: (s: string) => (s ? new Date(s + (s.length === 10 ? "T00:00:00" : "")).toLocaleDateString(undefined, { month: "short", day: "2-digit", year: "2-digit" }) : "—"),
};
