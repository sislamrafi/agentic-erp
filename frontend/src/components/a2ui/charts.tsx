"use client";
import {
  Area, AreaChart, Bar, BarChart, CartesianGrid, Cell, Legend, Line, LineChart, Pie, PieChart,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { fmt } from "@/lib/api";

const NAMED: Record<string, string> = { green: "#16a34a", red: "#f43f5e", black: "#0c0d0c", lime: "#a3e635", amber: "#f59e0b", blue: "#3b82f6" };
export const PALETTE = ["#16a34a", "#a3e635", "#0c0d0c", "#f59e0b", "#f43f5e", "#3b82f6", "#14b8a6", "#8b5cf6", "#94a3b8", "#65a30d"];
const color = (c: string | undefined, i: number) => (c && NAMED[c]) || c || PALETTE[i % PALETTE.length];

type Series = { key: string; label: string; color?: string };

function Tip({ active, payload, label, format }: any) {
  if (!active || !payload?.length) return null;
  const f = format === "money" ? fmt.money : fmt.num;
  return (
    <div className="rounded-xl border border-line bg-white/95 px-3 py-2 text-xs shadow-xl backdrop-blur">
      <div className="mb-1 font-medium text-muted">{label ?? payload[0]?.name}</div>
      {payload.map((p: any) => (
        <div key={p.dataKey + p.name} className="flex items-center justify-between gap-6">
          <span className="flex items-center gap-1.5"><span className="h-2 w-2 rounded-full" style={{ background: p.color || p.payload?.fill }} />{p.name}</span>
          <span className="num font-semibold">{f(p.value)}</span>
        </div>
      ))}
    </div>
  );
}

export function Chart({ chartType = "bar", data = [], series = [], height = 260, format, xKey = "label" }:
  { chartType?: string; data: any[]; series: Series[]; height?: number; format?: string; xKey?: string }) {
  const tick = { fontSize: 11, fill: "#9a9e98" };
  const yFmt = (v: number) => (format === "money" ? `$${fmt.compact(v)}` : fmt.compact(v));
  const axes = (
    <>
      <CartesianGrid vertical={false} stroke="#eef0ec" />
      <XAxis dataKey={xKey} tick={tick} axisLine={false} tickLine={false} />
      <YAxis tick={tick} axisLine={false} tickLine={false} tickFormatter={yFmt} width={48} />
      <Tooltip content={<Tip format={format} />} cursor={{ fill: "rgba(22,163,74,.06)", stroke: "#d4d8d1" }} />
    </>
  );
  const legend = series.length > 1 ? <Legend iconType="circle" iconSize={8} wrapperStyle={{ fontSize: 12, paddingTop: 8 }} /> : null;

  if (chartType === "pie" || chartType === "donut") {
    const s = series[0] || { key: "value", label: "Value" };
    return (
      <div className="flex items-center gap-4" style={{ height }}>
        <ResponsiveContainer width="55%" height="100%">
          <PieChart>
            <Pie data={data} dataKey={s.key} nameKey={xKey} innerRadius={chartType === "donut" ? "62%" : 0} outerRadius="92%" paddingAngle={chartType === "donut" ? 2 : 0} stroke="none">
              {data.map((_, i) => <Cell key={i} fill={PALETTE[i % PALETTE.length]} />)}
            </Pie>
            <Tooltip content={<Tip format={format} />} />
          </PieChart>
        </ResponsiveContainer>
        <div className="flex-1 space-y-1.5 overflow-auto text-xs scroll-thin" style={{ maxHeight: height }}>
          {data.map((d, i) => (
            <div key={i} className="flex items-center justify-between gap-2">
              <span className="flex items-center gap-2 truncate capitalize"><span className="h-2.5 w-2.5 shrink-0 rounded-[4px]" style={{ background: PALETTE[i % PALETTE.length] }} />{String(d[xKey]).replace("_", " ")}</span>
              <span className="num font-medium">{format === "money" ? fmt.money(d[s.key]) : fmt.num(d[s.key])}</span>
            </div>
          ))}
        </div>
      </div>
    );
  }
  if (chartType === "line") {
    return (
      <ResponsiveContainer width="100%" height={height}>
        <LineChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
          {axes}{legend}
          {series.map((s, i) => <Line key={s.key} type="monotone" dataKey={s.key} name={s.label} stroke={color(s.color, i)} strokeWidth={2.2} dot={false} activeDot={{ r: 4 }} />)}
        </LineChart>
      </ResponsiveContainer>
    );
  }
  if (chartType === "area") {
    return (
      <ResponsiveContainer width="100%" height={height}>
        <AreaChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
          <defs>{series.map((s, i) => (
            <linearGradient key={s.key} id={`g-${s.key}`} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={color(s.color, i)} stopOpacity={0.28} /><stop offset="100%" stopColor={color(s.color, i)} stopOpacity={0} />
            </linearGradient>))}
          </defs>
          {axes}{legend}
          {series.map((s, i) => <Area key={s.key} type="monotone" dataKey={s.key} name={s.label} stroke={color(s.color, i)} fill={`url(#g-${s.key})`} strokeWidth={2} />)}
        </AreaChart>
      </ResponsiveContainer>
    );
  }
  const horizontal = chartType === "hbar";
  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={data} layout={horizontal ? "vertical" : "horizontal"} margin={{ top: 8, right: 8, left: 0, bottom: 0 }} barGap={3}>
        <CartesianGrid vertical={horizontal} horizontal={!horizontal} stroke="#eef0ec" />
        {horizontal ? (
          <>
            <XAxis type="number" tick={tick} axisLine={false} tickLine={false} tickFormatter={yFmt} />
            <YAxis type="category" dataKey={xKey} tick={tick} axisLine={false} tickLine={false} width={120} />
          </>
        ) : (
          <>
            <XAxis dataKey={xKey} tick={tick} axisLine={false} tickLine={false} />
            <YAxis tick={tick} axisLine={false} tickLine={false} tickFormatter={yFmt} width={48} />
          </>
        )}
        <Tooltip content={<Tip format={format} />} cursor={{ fill: "rgba(22,163,74,.06)" }} />
        {legend}
        {series.map((s, i) => (
          <Bar key={s.key} dataKey={s.key} name={s.label} fill={color(s.color, i)} radius={horizontal ? [0, 6, 6, 0] : [6, 6, 0, 0]} maxBarSize={horizontal ? 18 : 26}>
            {series.length === 1 && !s.color && data.map((_, j) => <Cell key={j} fill={j % 2 ? "#a3e635" : "#16a34a"} />)}
          </Bar>
        ))}
      </BarChart>
    </ResponsiveContainer>
  );
}

export function Spark({ values, tone }: { values: number[]; tone?: string }) {
  const c = tone === "danger" ? "#f43f5e" : tone === "warning" ? "#f59e0b" : "#16a34a";
  const data = values.map((v, i) => ({ i, v }));
  const id = `sp-${tone}-${values.length}-${Math.round(values[0] || 0)}`;
  return (
    <ResponsiveContainer width="100%" height={40}>
      <AreaChart data={data} margin={{ top: 2, right: 0, left: 0, bottom: 0 }}>
        <defs><linearGradient id={id} x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor={c} stopOpacity={0.25} /><stop offset="100%" stopColor={c} stopOpacity={0} /></linearGradient></defs>
        <Area type="monotone" dataKey="v" stroke={c} fill={`url(#${id})`} strokeWidth={1.8} isAnimationActive={false} />
      </AreaChart>
    </ResponsiveContainer>
  );
}
