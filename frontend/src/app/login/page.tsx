"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowRight, Bot, Loader2 } from "lucide-react";
import { api, auth } from "@/lib/api";
import { Logo } from "@/components/Shell";

export default function Login() {
  const router = useRouter();
  const [email, setEmail] = useState("sislamrafi333@gmail.com");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true); setErr("");
    try {
      const r = await api<{ token: string }>("/api/auth/login", { method: "POST", body: JSON.stringify({ email, password }) });
      auth.set(r.token);
      router.replace("/agent");
    } catch (e: any) { setErr(e.message); } finally { setBusy(false); }
  };

  return (
    <div className="grid min-h-screen lg:grid-cols-2">
      <div className="flex flex-col justify-between p-8 lg:p-12">
        <Logo />
        <form onSubmit={submit} className="mx-auto w-full max-w-sm">
          <h1 className="text-3xl font-semibold tracking-tight">Welcome back</h1>
          <p className="mt-1.5 text-sm text-muted">Sign in to your agentic ERP workspace.</p>
          <div className="mt-8 flex flex-col gap-4">
            <label className="flex flex-col gap-1.5"><span className="text-xs font-medium text-muted">Email</span>
              <input value={email} onChange={(e) => setEmail(e.target.value)} className="h-11 rounded-xl border border-line bg-white px-3.5 text-sm outline-none focus:border-brand focus:ring-4 focus:ring-brand/10" /></label>
            <label className="flex flex-col gap-1.5"><span className="text-xs font-medium text-muted">Password</span>
              <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} className="h-11 rounded-xl border border-line bg-white px-3.5 text-sm outline-none focus:border-brand focus:ring-4 focus:ring-brand/10" /></label>
            {err && <div className="rounded-lg bg-rose-50 px-3 py-2 text-sm text-danger">{err}</div>}
            <button disabled={busy} className="mt-2 inline-flex h-11 items-center justify-center gap-2 rounded-xl bg-ink text-sm font-medium text-white transition hover:bg-ink/85 disabled:opacity-60">
              {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <>Sign in <ArrowRight className="h-4 w-4" /></>}
            </button>
            <p className="text-center text-xs text-faint">Demo password lives in <code>backend/app/seed.py</code></p>
          </div>
        </form>
        <p className="text-xs text-faint">© NextERP · Agentic ERP for SMBs</p>
      </div>
      <div className="relative hidden overflow-hidden bg-ink p-12 lg:flex lg:flex-col lg:justify-center">
        <div className="absolute -right-32 -top-32 h-96 w-96 rounded-full bg-lime/20 blur-3xl" />
        <div className="absolute -bottom-40 left-10 h-96 w-96 rounded-full bg-brand/30 blur-3xl" />
        <div className="relative max-w-lg">
          <span className="rounded-full border border-white/15 px-3 py-1 text-xs text-white/70">Generative UI · Google A2UI</span>
          <h2 className="mt-6 text-4xl font-semibold leading-tight tracking-tight text-white">Run your business by <span className="text-lime">talking to it.</span></h2>
          <p className="mt-4 text-white/60">Invoices, inventory, payroll and reports — your agent queries, creates and updates records, then renders live interfaces on the fly.</p>
          <div className="mt-10 space-y-3">
            {["Show me overdue invoices and remind me who owes the most", "Add an expense of $420 for fuel from Shell today", "Chart monthly revenue vs costs"].map((t, i) => (
              <div key={t} className="rise flex items-center gap-3 rounded-2xl border border-white/10 bg-white/5 p-3.5 text-sm text-white/85 backdrop-blur" style={{ animationDelay: `${i * 120}ms` }}>
                <span className="grid h-7 w-7 place-items-center rounded-lg bg-lime/15"><Bot className="h-4 w-4 text-lime" /></span>{t}
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
