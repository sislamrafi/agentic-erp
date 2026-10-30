"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import clsx from "clsx";
import { ArrowUp, Check, ChevronRight, LoaderCircle, MessageSquare, PanelLeft, Plus, Sparkles, Square, Trash2, TriangleAlert } from "lucide-react";
import { api, streamSSE } from "@/lib/api";
import { useErp } from "@/lib/erp";
import { LiveSurface } from "@/components/a2ui/LiveSurface";

type Part = { t: "text"; text: string } | { t: "tool"; id: string; name: string; label: string; status: string }
  | { t: "surface"; id: string; spec?: any; messages?: any[] };
type Msg = { id: string | number; role: "user" | "assistant"; content: string; parts: Part[]; reasoning?: string; streaming?: boolean };
type Conv = { id: number; title: string; updated_at: string };

const SUGGESTIONS = [
  { icon: "📊", title: "Business pulse", prompt: "Show me my dashboard and summarize what needs attention" },
  { icon: "🧾", title: "Chase payments", prompt: "Which invoices are overdue? Show them in a table and tell me who owes the most" },
  { icon: "➕", title: "Create invoice", prompt: "Create a new invoice for NexaCorp for $3,200 due in 30 days" },
  { icon: "📦", title: "Inventory check", prompt: "Which products are low on stock? Show a chart of stock by category" },
  { icon: "💸", title: "Cost analysis", prompt: "Chart my expenses by category and tell me where I can cut costs" },
  { icon: "👥", title: "Payroll view", prompt: "Show payroll by department as a donut chart" },
];

export function Chat() {
  const router = useRouter();
  const search = useSearchParams();
  const { user, toast } = useErp();
  const [convs, setConvs] = useState<Conv[]>([]);
  const [convId, setConvId] = useState<number | null>(null);
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [side, setSide] = useState(true);
  const abort = useRef<AbortController | null>(null);
  const bottom = useRef<HTMLDivElement>(null);
  const autoSent = useRef(false);

  const loadConvs = useCallback(() => api<Conv[]>("/api/conversations").then(setConvs).catch(() => {}), []);
  useEffect(() => { loadConvs(); }, [loadConvs]);
  useEffect(() => { bottom.current?.scrollIntoView({ behavior: "smooth", block: "end" }); }, [msgs]);

  const openConv = async (id: number) => {
    if (busy) return;
    const c = await api<{ messages: Msg[] }>(`/api/conversations/${id}`);
    setConvId(id);
    setMsgs(c.messages);
  };

  const newChat = () => { if (!busy) { setConvId(null); setMsgs([]); } };

  const send = useCallback(async (text: string) => {
    const q = text.trim();
    if (!q || busy) return;
    setInput("");
    setBusy(true);
    const aid = `a-${Date.now()}`;
    setMsgs((m) => [...m, { id: `u-${Date.now()}`, role: "user", content: q, parts: [] },
      { id: aid, role: "assistant", content: "", parts: [], streaming: true }]);
    const patch = (fn: (m: Msg) => Msg) => setMsgs((all) => all.map((m) => (m.id === aid ? fn(m) : m)));
    abort.current = new AbortController();
    try {
      for await (const ev of streamSSE("/api/chat", { message: q, conversation_id: convId }, abort.current.signal)) {
        if (ev.type === "conversation") { setConvId(ev.id); }
        else if (ev.type === "reasoning") patch((m) => ({ ...m, reasoning: (m.reasoning || "") + ev.text }));
        else if (ev.type === "token") patch((m) => {
          const parts = [...m.parts];
          const last = parts[parts.length - 1];
          if (last?.t === "text") parts[parts.length - 1] = { ...last, text: last.text + ev.text };
          else parts.push({ t: "text", text: ev.text });
          return { ...m, content: m.content + ev.text, parts };
        });
        else if (ev.type === "tool_start") patch((m) => ({ ...m, parts: [...m.parts, { t: "tool", id: ev.id, name: ev.name, label: ev.label, status: "running" }] }));
        else if (ev.type === "tool_end") patch((m) => ({ ...m, parts: m.parts.map((p) => (p.t === "tool" && p.id === ev.id ? { ...p, status: ev.ok ? "done" : "error" } : p)) }));
        else if (ev.type === "surface") patch((m) => ({ ...m, parts: [...m.parts, ev.part] }));
      }
    } catch (e: any) {
      if (e.name !== "AbortError") toast(e.message || "Agent failed", "error");
    } finally {
      patch((m) => ({ ...m, streaming: false }));
      setBusy(false);
      loadConvs();
    }
  }, [busy, convId, loadConvs, toast]);

  useEffect(() => {
    const q = search.get("q");
    if (q && !autoSent.current) { autoSent.current = true; router.replace("/agent"); send(q); }
  }, [search, router, send]);

  const del = async (id: number) => {
    await api(`/api/conversations/${id}`, { method: "DELETE" });
    if (id === convId) newChat();
    loadConvs();
  };

  const empty = msgs.length === 0;

  return (
    <div className="flex h-[calc(100vh-56px)]">
      {side && (
        <aside className="hidden w-64 shrink-0 flex-col border-r border-line bg-white/60 md:flex">
          <div className="p-3">
            <button onClick={newChat} className="flex h-9 w-full items-center gap-2 rounded-xl border border-line bg-white px-3 text-sm font-medium hover:bg-canvas">
              <Plus className="h-4 w-4" />New chat
            </button>
          </div>
          <div className="px-4 pb-1 text-[11px] font-medium uppercase tracking-wider text-faint">History</div>
          <div className="flex-1 overflow-y-auto px-2 pb-3 scroll-thin">
            {convs.map((c) => (
              <div key={c.id} className={clsx("group flex items-center gap-2 rounded-lg px-2.5 py-2 text-sm transition", c.id === convId ? "bg-canvas font-medium" : "text-ink/75 hover:bg-canvas/70")}>
                <MessageSquare className="h-3.5 w-3.5 shrink-0 text-faint" />
                <button onClick={() => openConv(c.id)} className="flex-1 truncate text-left">{c.title}</button>
                <button onClick={() => del(c.id)} className="opacity-0 transition group-hover:opacity-100"><Trash2 className="h-3.5 w-3.5 text-faint hover:text-danger" /></button>
              </div>
            ))}
            {!convs.length && <div className="px-3 py-2 text-xs text-faint">No conversations yet.</div>}
          </div>
        </aside>
      )}

      <section className="relative flex min-w-0 flex-1 flex-col">
        <button onClick={() => setSide((s) => !s)} className="absolute left-3 top-3 z-10 hidden h-8 w-8 place-items-center rounded-lg text-muted hover:bg-white md:grid"><PanelLeft className="h-4 w-4" /></button>
        <div className="flex-1 overflow-y-auto scroll-thin">
          {empty ? (
            <div className="glow flex min-h-full flex-col items-center justify-center px-6 pb-10">
              <div className="grid h-14 w-14 place-items-center rounded-2xl bg-ink shadow-xl shadow-brand/20"><Sparkles className="h-6 w-6 text-lime" /></div>
              <h1 className="mt-5 text-center text-3xl font-semibold tracking-tight">How can I run the business for you{user ? `, ${user.name.split(" ")[0]}` : ""}?</h1>
              <p className="mt-2 text-center text-sm text-muted">Ask anything. I read and change your ERP data and render live, interactive UI right here.</p>
              <div className="mt-8 w-full max-w-3xl"><Composer value={input} onChange={setInput} onSend={() => send(input)} busy={busy} onStop={() => abort.current?.abort()} big /></div>
              <div className="mt-6 grid w-full max-w-3xl grid-cols-2 gap-2.5 md:grid-cols-3">
                {SUGGESTIONS.map((s, i) => (
                  <button key={s.title} onClick={() => send(s.prompt)} style={{ animationDelay: `${i * 60}ms` }}
                    className="rise card group flex flex-col gap-1 p-3.5 text-left transition hover:-translate-y-0.5 hover:shadow-md">
                    <span className="text-lg">{s.icon}</span>
                    <span className="text-sm font-medium">{s.title}</span>
                    <span className="line-clamp-2 text-xs text-muted">{s.prompt}</span>
                  </button>
                ))}
              </div>
            </div>
          ) : (
            <div className="mx-auto flex max-w-4xl flex-col gap-6 px-6 py-8">
              {msgs.map((m) => <Message key={m.id} m={m} />)}
              <div ref={bottom} className="h-4" />
            </div>
          )}
        </div>
        {!empty && (
          <div className="border-t border-line/60 bg-gradient-to-t from-canvas via-canvas to-canvas/0 px-6 pb-5 pt-3">
            <div className="mx-auto max-w-4xl"><Composer value={input} onChange={setInput} onSend={() => send(input)} busy={busy} onStop={() => abort.current?.abort()} /></div>
          </div>
        )}
      </section>
    </div>
  );
}

function Composer({ value, onChange, onSend, busy, onStop, big }: { value: string; onChange: (v: string) => void; onSend: () => void; busy: boolean; onStop: () => void; big?: boolean }) {
  const ref = useRef<HTMLTextAreaElement>(null);
  useEffect(() => {
    if (ref.current) { ref.current.style.height = "auto"; ref.current.style.height = Math.min(ref.current.scrollHeight, 200) + "px"; }
  }, [value]);
  return (
    <div className="card flex items-end gap-2 p-2 shadow-lg shadow-ink/[.04] transition focus-within:border-brand/40 focus-within:ring-4 focus-within:ring-brand/10">
      <textarea ref={ref} rows={1} value={value} autoFocus onChange={(e) => onChange(e.target.value)}
        onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); onSend(); } }}
        placeholder="Ask your ERP agent… e.g. “Add a customer called Acme in Austin”"
        className={clsx("flex-1 resize-none bg-transparent px-3 text-[15px] outline-none placeholder:text-faint", big ? "py-3" : "py-2")} />
      {busy ? (
        <button onClick={onStop} className="grid h-10 w-10 place-items-center rounded-xl bg-ink text-white"><Square className="h-3.5 w-3.5 fill-white" /></button>
      ) : (
        <button onClick={onSend} disabled={!value.trim()} className="grid h-10 w-10 place-items-center rounded-xl bg-ink text-white transition disabled:bg-line disabled:text-faint"><ArrowUp className="h-4 w-4" /></button>
      )}
    </div>
  );
}

function Message({ m }: { m: Msg }) {
  const [showR, setShowR] = useState(false);
  if (m.role === "user") {
    return <div className="rise flex justify-end"><div className="max-w-[80%] whitespace-pre-wrap rounded-2xl rounded-br-md bg-ink px-4 py-2.5 text-[15px] text-white">{m.content}</div></div>;
  }
  const thinking = m.streaming && m.parts.length === 0;
  return (
    <div className="rise flex gap-3">
      <div className="mt-0.5 grid h-8 w-8 shrink-0 place-items-center rounded-xl bg-ink"><Sparkles className="h-4 w-4 text-lime" /></div>
      <div className="flex min-w-0 flex-1 flex-col gap-3">
        {(thinking || m.reasoning) && (
          <button onClick={() => setShowR((s) => !s)} className="flex w-fit items-center gap-2 text-xs text-muted">
            {thinking ? <span className="flex gap-1"><span className="dot h-1.5 w-1.5 rounded-full bg-brand" /><span className="dot h-1.5 w-1.5 rounded-full bg-brand [animation-delay:.2s]" /><span className="dot h-1.5 w-1.5 rounded-full bg-brand [animation-delay:.4s]" /></span> : <ChevronRight className={clsx("h-3 w-3 transition", showR && "rotate-90")} />}
            {thinking ? "Thinking…" : "Reasoning"}
          </button>
        )}
        {showR && m.reasoning && <div className="whitespace-pre-wrap rounded-xl border border-line bg-white/60 p-3 text-xs text-muted">{m.reasoning}</div>}
        {groupParts(m.parts).map((g, i) => {
          if (g.kind === "tools") {
            return (
              <div key={i} className="flex flex-wrap gap-1.5">
                {g.items.map((p: any) => (
                  <span key={p.id} className={clsx("inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[11px] font-medium",
                    p.status === "error" ? "border-rose-200 bg-rose-50 text-danger" : p.status === "done" ? "border-line bg-white text-muted" : "border-brand/30 bg-brand-soft text-brand")}>
                    {p.status === "running" ? <LoaderCircle className="h-3 w-3 animate-spin" /> : p.status === "error" ? <TriangleAlert className="h-3 w-3" /> : <Check className="h-3 w-3 text-brand" />}
                    {p.label}
                  </span>
                ))}
              </div>
            );
          }
          const p = g.part as Part;
          if (p.t === "text") {
            return (
              <div key={i} className="prose-chat text-[15px] leading-relaxed text-ink/90">
                <ReactMarkdown remarkPlugins={[[remarkGfm, { singleTilde: false }]]}>{p.text}</ReactMarkdown>
              </div>
            );
          }
          if (p.t === "surface") {
            return (
              <div key={p.id} className="rise">
                <LiveSurface surfaceId={p.messages ? p.messages[0]?.surfaceUpdate?.surfaceId ?? p.id : `chat-${p.id}`} spec={p.spec} messages={p.messages} />
                {p.spec && p.spec.live !== false && <div className="mt-1.5 flex items-center gap-1.5 text-[11px] text-faint"><span className="dot h-1.5 w-1.5 rounded-full bg-brand" />Live A2UI surface · {p.spec.screen}</div>}
              </div>
            );
          }
          return null;
        })}
        {m.streaming && m.parts.length > 0 && m.parts[m.parts.length - 1].t !== "text" && (
          <span className="flex gap-1"><span className="dot h-1.5 w-1.5 rounded-full bg-faint" /><span className="dot h-1.5 w-1.5 rounded-full bg-faint [animation-delay:.2s]" /><span className="dot h-1.5 w-1.5 rounded-full bg-faint [animation-delay:.4s]" /></span>
        )}
      </div>
    </div>
  );
}

function groupParts(parts: Part[]) {
  const out: { kind: "tools" | "part"; items: any[]; part?: Part }[] = [];
  for (const p of parts) {
    if (p.t === "tool") {
      const last = out[out.length - 1];
      if (last?.kind === "tools") last.items.push(p);
      else out.push({ kind: "tools", items: [p] });
    } else out.push({ kind: "part", items: [], part: p });
  }
  return out;
}
