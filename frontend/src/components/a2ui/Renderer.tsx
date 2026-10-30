"use client";
import { createContext, useContext, useState } from "react";
import clsx from "clsx";
import { ChevronDown, TrendingDown, TrendingUp } from "lucide-react";
import { fmt } from "@/lib/api";
import { getPath, resolve, resolveContext, type SurfaceState } from "@/lib/a2ui";
import { Chart, PALETTE, Spark } from "./charts";
import { Icon } from "./icons";

type RCtx = {
  surface: SurfaceState;
  setData: (path: string, value: any) => void;
  dispatch: (name: string, context: Record<string, any>, sourceId?: string) => void;
};
const Ctx = createContext<RCtx>(null as any);

export function A2Renderer({ surface, setData, dispatch }: RCtx) {
  if (!surface?.root || !surface.components[surface.root]) return null;
  return (
    <Ctx.Provider value={{ surface, setData, dispatch }}>
      <Node id={surface.root} />
    </Ctx.Provider>
  );
}

function Node({ id }: { id: string }) {
  const { surface } = useContext(Ctx);
  const c = surface.components[id];
  if (!c) return null;
  const [type, props] = Object.entries(c.component)[0] as [string, any];
  const Comp = CATALOG[type];
  if (!Comp) return <div className="rounded-lg border border-dashed border-line p-2 text-xs text-faint">Unsupported component: {type}</div>;
  return <Comp id={id} {...props} />;
}

const kids = (children: any): string[] => children?.explicitList || [];
const GAP: Record<string, string> = { none: "gap-0", xs: "gap-1", sm: "gap-2", md: "gap-3", lg: "gap-5" };
const useV = () => { const { surface } = useContext(Ctx); return (v: any) => resolve(v, surface.data); };
const TONE_BG: Record<string, string> = {
  success: "bg-brand-soft text-brand", warning: "bg-amber-50 text-amber-700", danger: "bg-rose-50 text-rose-600",
  info: "bg-blue-50 text-blue-600", neutral: "bg-stone-100 text-stone-600",
};

function Badge({ label, tone = "neutral" }: any) {
  return <span className={clsx("inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-medium capitalize", TONE_BG[tone] || TONE_BG.neutral)}>
    <span className="h-1.5 w-1.5 rounded-full bg-current opacity-70" />{String(label ?? "").replace("_", " ")}</span>;
}

function Avatar({ name }: { name: string }) {
  const n = name || "?";
  const i = [...n].reduce((a, ch) => a + ch.charCodeAt(0), 0) % PALETTE.length;
  return <span className="grid h-7 w-7 shrink-0 place-items-center rounded-lg text-[11px] font-semibold text-white" style={{ background: PALETTE[i] }}>{n.slice(0, 1)}</span>;
}

function formatCell(v: any, type: string, tones?: Record<string, string>) {
  if (v == null || v === "") return <span className="text-faint">—</span>;
  switch (type) {
    case "money": return <span className="num font-medium">{fmt.money(v)}</span>;
    case "number": return <span className="num">{fmt.num(v)}</span>;
    case "percent": return <span className="num">{fmt.pct(v)}</span>;
    case "date": return <span className="num text-muted">{fmt.date(v)}</span>;
    case "badge": return <Badge label={v} tone={tones?.[v] || "neutral"} />;
    case "avatar": return <span className="flex items-center gap-2"><Avatar name={String(v)} /><span className="font-medium">{v}</span></span>;
    case "email": return <span className="text-muted">{v}</span>;
    default: return <span>{String(v)}</span>;
  }
}

const CATALOG: Record<string, (p: any) => any> = {
  Column: ({ children, gap = "md" }) => <div className={clsx("flex min-w-0 flex-col", GAP[gap])}>{kids(children).map((k) => <Node key={k} id={k} />)}</div>,
  Row: ({ children, gap = "md", distribution, alignment }) => (
    <div className={clsx("flex min-w-0 flex-wrap", GAP[gap], alignment === "start" ? "items-start" : alignment === "end" ? "items-end" : "items-center",
      distribution === "spaceBetween" && "justify-between", distribution === "end" && "justify-end", distribution === "center" && "justify-center")}>
      {kids(children).map((k) => <Node key={k} id={k} />)}
    </div>),
  Grid: ({ children, columns = 2 }) => (
    <div className={clsx("grid gap-4", { 1: "grid-cols-1", 2: "grid-cols-1 lg:grid-cols-2", 3: "grid-cols-1 md:grid-cols-2 xl:grid-cols-3", 4: "grid-cols-2 xl:grid-cols-4" }[columns as 1] || "grid-cols-2")}>
      {kids(children).map((k) => <Node key={k} id={k} />)}
    </div>),
  Spacer: () => <div className="flex-1" />,
  Card: ({ child, padding, tone }) => (
    <div className={clsx("card rise min-w-0 overflow-hidden", padding === "none" ? "" : "p-5", tone === "success" && "border-brand/25 bg-gradient-to-br from-brand-soft/70 to-white")}><Node id={child} /></div>),
  Divider: () => <hr className="border-line" />,
  Icon: ({ name }) => { const v = useV(); return <span className="grid h-9 w-9 place-items-center rounded-xl bg-brand-soft text-brand"><Icon name={v(name)} /></span>; },
  Text: ({ text, usageHint = "body" }) => {
    const v = useV();
    const s = v(text);
    const cls: Record<string, string> = {
      h1: "text-3xl font-semibold tracking-tight", h2: "text-2xl font-semibold tracking-tight", h3: "text-[15px] font-semibold",
      h4: "text-sm font-semibold", h5: "text-sm font-medium", caption: "text-xs text-muted", label: "text-sm font-medium", body: "text-sm text-ink/80 leading-relaxed",
    };
    return <div className={cls[usageHint] || cls.body}>{s}</div>;
  },
  Image: ({ url }) => { const v = useV(); return <img src={v(url)} alt="" className="max-h-64 rounded-xl object-cover" />; },
  Button: ({ id, child, action, variant, primary, icon }) => {
    const { surface, dispatch } = useContext(Ctx);
    const [busy, setBusy] = useState(false);
    const vt = variant || (primary ? "primary" : "secondary");
    return (
      <button disabled={busy} onClick={async () => {
        setBusy(true);
        try { await dispatch(action.name, resolveContext(action.context, surface.data), id); } finally { setBusy(false); }
      }} className={clsx("inline-flex h-9 items-center gap-1.5 rounded-xl px-3.5 text-sm font-medium transition active:scale-[.98] disabled:opacity-60",
        vt === "primary" && "bg-ink text-white hover:bg-ink/85",
        vt === "secondary" && "border border-line bg-white hover:bg-canvas",
        vt === "ghost" && "text-muted hover:bg-canvas hover:text-ink")}>
        {icon && <Icon name={icon} className="h-3.5 w-3.5" />}<Node id={child} />
      </button>
    );
  },
  TextField: ({ id, label, text, textFieldType = "shortText", placeholder, onSubmit }) => {
    const { surface, setData, dispatch } = useContext(Ctx);
    const v = useV();
    const p = text?.path;
    const val = p ? getPath(surface.data, p) ?? "" : v(text) ?? "";
    const common = "w-full rounded-xl border border-line bg-white px-3 text-sm outline-none transition focus:border-brand focus:ring-4 focus:ring-brand/10";
    const submit = () => onSubmit && dispatch(onSubmit.name, resolveContext(onSubmit.context, surface.data), id);
    return (
      <label className={clsx("flex flex-col gap-1.5", textFieldType === "longText" && "col-span-full", textFieldType === "search" && "min-w-[260px] flex-1 max-w-md")}>
        {v(label) && <span className="text-xs font-medium text-muted">{v(label)}</span>}
        {textFieldType === "longText" ? (
          <textarea rows={3} className={clsx(common, "py-2")} value={val} placeholder={placeholder} onChange={(e) => p && setData(p, e.target.value)} />
        ) : (
          <div className="relative">
            {textFieldType === "search" && <Icon name="search" className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-faint" />}
            <input className={clsx(common, "h-10", textFieldType === "search" && "pl-9")} value={val} placeholder={placeholder}
              type={{ number: "number", date: "date", email: "email", obscured: "password" }[textFieldType as string] || "text"}
              step={textFieldType === "number" ? "any" : undefined}
              onChange={(e) => p && setData(p, textFieldType === "number" && e.target.value !== "" ? Number(e.target.value) : e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && submit()} />
          </div>
        )}
      </label>
    );
  },
  CheckBox: ({ label, value }) => {
    const { surface, setData } = useContext(Ctx);
    const v = useV();
    return <label className="flex items-center gap-2 text-sm"><input type="checkbox" className="accent-brand" checked={!!getPath(surface.data, value?.path)} onChange={(e) => setData(value.path, e.target.checked)} />{v(label)}</label>;
  },
  MultipleChoice: ({ id, label, selections, options = [], variant = "select", onChange }) => {
    const { surface, setData, dispatch } = useContext(Ctx);
    const v = useV();
    const p = selections?.path;
    const cur = String(getPath(surface.data, p) ?? "");
    const set = (val: string) => {
      setData(p, val);
      if (onChange) dispatch(onChange.name, resolveContext(onChange.context, { ...surface.data, ...nestSet(surface.data, p, val) }), id);
    };
    if (variant === "chips") {
      return (
        <div className="flex flex-wrap items-center gap-1 rounded-xl border border-line bg-white p-1">
          {options.map((o: any) => (
            <button key={o.value} onClick={() => set(o.value)} className={clsx("rounded-lg px-3 py-1.5 text-xs font-medium transition",
              cur === o.value ? "bg-ink text-white shadow-sm" : "text-muted hover:bg-canvas hover:text-ink")}>{v(o.label)}</button>
          ))}
        </div>
      );
    }
    return (
      <label className="flex flex-col gap-1.5">
        {v(label) && <span className="text-xs font-medium text-muted">{v(label)}</span>}
        <div className="relative">
          <select value={cur} onChange={(e) => set(e.target.value)} className="h-10 w-full appearance-none rounded-xl border border-line bg-white px-3 pr-8 text-sm capitalize outline-none focus:border-brand focus:ring-4 focus:ring-brand/10">
            <option value="">Select…</option>
            {options.map((o: any) => <option key={o.value} value={o.value}>{v(o.label)}</option>)}
          </select>
          <ChevronDown className="pointer-events-none absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-faint" />
        </div>
      </label>
    );
  },
  Tabs: ({ tabItems = [] }) => {
    const [i, setI] = useState(0);
    const v = useV();
    return (
      <div className="flex flex-col gap-3">
        <div className="flex gap-1 border-b border-line">
          {tabItems.map((t: any, j: number) => (
            <button key={j} onClick={() => setI(j)} className={clsx("-mb-px border-b-2 px-3 py-2 text-xs font-medium transition",
              i === j ? "border-ink text-ink" : "border-transparent text-muted hover:text-ink")}>{v(t.title)}</button>
          ))}
        </div>
        {tabItems[i] && <Node id={tabItems[i].child} />}
      </div>
    );
  },
  List: ({ children, direction }) => <div className={clsx("flex gap-2", direction === "horizontal" ? "flex-row overflow-x-auto" : "flex-col")}>{kids(children).map((k) => <Node key={k} id={k} />)}</div>,

  // ---------------- custom catalog
  Badge: ({ label, tone }) => { const v = useV(); return <Badge label={v(label)} tone={tone} />; },
  Alert: ({ title, body, tone = "info" }) => {
    const v = useV();
    return (
      <div className={clsx("flex gap-3 rounded-xl border p-3.5", { info: "border-blue-100 bg-blue-50/60", warning: "border-amber-100 bg-amber-50/70", danger: "border-rose-100 bg-rose-50/70", success: "border-green-100 bg-brand-soft/60" }[tone as string])}>
        <Icon name={tone === "success" ? "check-circle" : tone === "info" ? "info" : "warning"} className={clsx("mt-0.5 h-4 w-4 shrink-0", TONE_BG[tone]?.split(" ")[1])} />
        <div><div className="text-sm font-semibold">{v(title)}</div>{body && <div className="mt-0.5 text-sm text-ink/70">{v(body)}</div>}</div>
      </div>
    );
  },
  Metric: ({ label, value, delta, sub, spark, format, tone, invertDelta }) => {
    const v = useV();
    const val = v(value);
    const shown = format === "money" ? fmt.money(val) : format === "percent" ? fmt.pct(val) : typeof val === "number" ? fmt.num(val) : val;
    const d = v(delta);
    const good = d == null ? null : invertDelta ? d <= 0 : d >= 0;
    return (
      <div className="card rise flex min-w-0 flex-col gap-2 p-4">
        <div className="flex items-center justify-between">
          <span className="text-[11px] font-medium uppercase tracking-wider text-muted">{v(label)}</span>
          {tone && <span className={clsx("h-2 w-2 rounded-full", { success: "bg-brand", warning: "bg-warn", danger: "bg-danger", info: "bg-info" }[tone as string])} />}
        </div>
        <div className="flex items-end gap-2">
          <span className="num text-2xl font-semibold tracking-tight">{shown}</span>
          {d != null && (
            <span className={clsx("mb-1 inline-flex items-center gap-0.5 rounded-md px-1.5 py-0.5 text-[11px] font-semibold", good ? "bg-brand-soft text-brand" : "bg-rose-50 text-rose-600")}>
              {d >= 0 ? <TrendingUp className="h-3 w-3" /> : <TrendingDown className="h-3 w-3" />}{Math.abs(d)}%
            </span>
          )}
        </div>
        {sub && <span className="text-xs text-faint">{v(sub)}</span>}
        {spark && spark.length > 1 && <div className="-mx-1 mt-auto"><Spark values={spark} tone={tone} /></div>}
      </div>
    );
  },
  Chart: (p) => (
    <div className="min-w-0">
      {p.title && <div className="mb-2 text-sm font-semibold">{p.title}</div>}
      <Chart {...p} />
    </div>),
  ProgressSegments: ({ items = [] }) => {
    const total = items.reduce((a: number, b: any) => a + (b.value || 0), 0) || 1;
    const col: Record<string, string> = { success: "bg-brand", warning: "bg-lime", danger: "bg-danger", info: "bg-info", neutral: "bg-stone-300" };
    return (
      <div className="flex flex-col gap-3">
        <div className="grid gap-3" style={{ gridTemplateColumns: `repeat(${items.length}, minmax(0,1fr))` }}>
          {items.map((it: any) => (
            <div key={it.label}>
              <div className="text-[11px] font-medium uppercase tracking-wider text-muted">{it.label}</div>
              <div className="num text-lg font-semibold">{fmt.money(it.value)}</div>
              <div className="text-[11px] text-faint">{((it.value / total) * 100).toFixed(1)}%</div>
            </div>
          ))}
        </div>
        <div className="flex h-2 overflow-hidden rounded-full bg-canvas">
          {items.map((it: any) => <div key={it.label} className={clsx(col[it.tone] || col.neutral, "transition-all duration-700")} style={{ width: `${(it.value / total) * 100}%` }} />)}
        </div>
      </div>
    );
  },
  BarList: ({ items = [], format }) => {
    const max = Math.max(...items.map((i: any) => i.value), 1);
    return (
      <div className="flex flex-col gap-2.5">
        {items.map((it: any, i: number) => (
          <div key={it.label} className="grid grid-cols-[110px_1fr_auto] items-center gap-3 text-sm">
            <span className="truncate text-ink/80">{it.label}</span>
            <div className="h-2 overflow-hidden rounded-full bg-canvas"><div className="h-full rounded-full transition-all duration-700" style={{ width: `${(it.value / max) * 100}%`, background: PALETTE[i % PALETTE.length] }} /></div>
            <span className="num w-28 text-right text-xs"><b className="font-semibold">{format === "money" ? fmt.money(it.value) : fmt.num(it.value)}</b>{it.share != null && <span className="ml-1.5 text-faint">{it.share}%</span>}</span>
          </div>
        ))}
      </div>
    );
  },
  KeyValue: ({ items = [], statusTones }) => (
    <div className="grid grid-cols-1 gap-x-8 gap-y-3 sm:grid-cols-2">
      {items.map((it: any) => (
        <div key={it.label} className="flex flex-col gap-0.5 border-b border-line/70 pb-2">
          <span className="text-[11px] font-medium uppercase tracking-wider text-muted">{it.label}</span>
          <span className="text-sm">{formatCell(it.value, it.type, statusTones)}</span>
        </div>
      ))}
    </div>
  ),
  DataTable: ({ id, resource, columns = [], rows = [], rowActions = [], statusTones, compact }) => {
    const { dispatch } = useContext(Ctx);
    const [confirm, setConfirm] = useState<string | null>(null);
    if (!rows.length) return <div className="grid place-items-center px-4 py-12 text-sm text-faint">No records found.</div>;
    return (
      <div className="overflow-x-auto scroll-thin">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-line text-left text-[11px] uppercase tracking-wider text-muted">
              {columns.map((c: any) => <th key={c.key} className={clsx("whitespace-nowrap px-4 py-2.5 font-medium", ["money", "number", "percent"].includes(c.type) && "text-right")}>{c.label}</th>)}
              {rowActions.length > 0 && <th className="w-px" />}
            </tr>
          </thead>
          <tbody>
            {rows.map((r: any, ri: number) => (
              <tr key={r.id ?? ri} className={clsx("group border-b border-line/60 transition last:border-0 hover:bg-canvas/70", resource && "cursor-pointer")}
                onClick={() => resource && r.id && dispatch("show_record", { resource, id: r.id }, id)}>
                {columns.map((c: any) => (
                  <td key={c.key} className={clsx("whitespace-nowrap px-4", compact ? "py-2" : "py-2.5", ["money", "number", "percent"].includes(c.type) && "text-right")}>{formatCell(r[c.key], c.type, statusTones)}</td>
                ))}
                {rowActions.length > 0 && (
                  <td className="px-2" onClick={(e) => e.stopPropagation()}>
                    <div className="flex justify-end gap-0.5 opacity-40 transition group-hover:opacity-100">
                      {rowActions.filter((a: any) => !a.when || Object.entries(a.when).every(([k, vals]: any) => vals.includes(r[k]))).map((a: any) => {
                        const key = `${a.name}-${r.id}`;
                        if (a.confirm && confirm === key) {
                          return <button key={a.name} onClick={() => { setConfirm(null); dispatch(a.name, { resource, id: r.id }, id); }}
                            className="rounded-lg bg-danger px-2 py-1 text-[11px] font-semibold text-white">Confirm</button>;
                        }
                        return (
                          <button key={a.name} title={a.label} onClick={() => (a.confirm ? setConfirm(key) : dispatch(a.name, { resource, id: r.id }, id))}
                            className={clsx("grid h-7 w-7 place-items-center rounded-lg transition", a.tone === "danger" ? "text-muted hover:bg-rose-50 hover:text-danger" : "text-muted hover:bg-white hover:text-ink hover:shadow-sm")}>
                            <Icon name={a.icon} className="h-3.5 w-3.5" />
                          </button>
                        );
                      })}
                    </div>
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  },
};

function nestSet(data: any, path: string, value: any) {
  const parts = path.split("/").filter(Boolean);
  const out: any = Array.isArray(data) ? [...data] : { ...data };
  let cur = out;
  parts.forEach((p, i) => {
    if (i === parts.length - 1) cur[p] = value;
    else { cur[p] = { ...(cur[p] || {}) }; cur = cur[p]; }
  });
  return out;
}
