"use client";
import { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { API, api, auth, User } from "./api";
import type { A2Message, UserAction } from "./a2ui";

type Toast = { id: number; text: string; tone: "success" | "error" | "info" };
export type ActionResult = { messages: A2Message[]; toast?: string; params?: any; target?: string; freeze?: boolean };
type DataEvent = { type: string; resource: string; action: string; id?: number; source?: string };

type Ctx = {
  user: User | null;
  toast: (text: string, tone?: Toast["tone"]) => void;
  drawer: A2Message[] | null;
  setDrawer: (m: A2Message[] | null) => void;
  onData: (fn: (e: DataEvent) => void) => () => void;
  sendAction: (a: UserAction) => Promise<ActionResult | null>;
  askAgent: (prompt: string) => void;
  live: boolean;
  activity: DataEvent[];
};

const ErpCtx = createContext<Ctx>(null as any);
export const useErp = () => useContext(ErpCtx);

export function ErpProvider({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);
  const [toasts, setToasts] = useState<Toast[]>([]);
  const [drawer, setDrawer] = useState<A2Message[] | null>(null);
  const [live, setLive] = useState(false);
  const [activity, setActivity] = useState<DataEvent[]>([]);
  const listeners = useRef(new Set<(e: DataEvent) => void>());

  useEffect(() => {
    if (!auth.token) { router.replace("/login"); return; }
    api<User>("/api/auth/me").then(setUser).catch(() => router.replace("/login"));
  }, [router]);

  // Realtime: one SSE connection fans out data_changed events to every live A2UI surface.
  useEffect(() => {
    if (!auth.token) return;
    let es: EventSource | null = null;
    let retry: any;
    const connect = () => {
      es = new EventSource(`${API}/api/events?token=${encodeURIComponent(auth.token!)}`);
      es.addEventListener("ready", () => setLive(true));
      es.onmessage = (m) => {
        try {
          const ev = JSON.parse(m.data);
          setActivity((a) => [ev, ...a].slice(0, 20));
          listeners.current.forEach((fn) => fn(ev));
        } catch {}
      };
      es.onerror = () => { setLive(false); es?.close(); retry = setTimeout(connect, 2000); };
    };
    connect();
    return () => { es?.close(); clearTimeout(retry); };
  }, []);

  const toast = useCallback((text: string, tone: Toast["tone"] = "success") => {
    const id = Date.now() + Math.random();
    setToasts((t) => [...t, { id, text, tone }]);
    setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), 3200);
  }, []);

  const onData = useCallback((fn: (e: DataEvent) => void) => {
    listeners.current.add(fn);
    return () => { listeners.current.delete(fn); };
  }, []);

  const askAgent = useCallback((prompt: string) => {
    router.push(`/agent?q=${encodeURIComponent(prompt)}`);
  }, [router]);

  const sendAction = useCallback(async (a: UserAction): Promise<ActionResult | null> => {
    if (a.name === "client:ask_agent") { askAgent(a.context.prompt); return null; }
    try {
      const res = await api<ActionResult>("/api/a2ui/action", { method: "POST", body: JSON.stringify({ userAction: a }) });
      if (res.toast) toast(res.toast);
      if (res.target === "drawer") { setDrawer(res.messages); return null; }
      return res;
    } catch (e: any) {
      toast(e.message || "Action failed", "error");
      return null;
    }
  }, [askAgent, toast]);

  return (
    <ErpCtx.Provider value={{ user, toast, drawer, setDrawer, onData, sendAction, askAgent, live, activity }}>
      {children}
      <div className="fixed bottom-5 right-5 z-[100] flex flex-col gap-2">
        {toasts.map((t) => (
          <div key={t.id} className={`rise flex items-center gap-2 rounded-xl px-4 py-2.5 text-sm font-medium text-white shadow-lg ${t.tone === "error" ? "bg-danger" : "bg-ink"}`}>
            <span className={`h-2 w-2 rounded-full ${t.tone === "error" ? "bg-white" : "bg-lime"}`} />
            {t.text}
          </div>
        ))}
      </div>
    </ErpCtx.Provider>
  );
}
