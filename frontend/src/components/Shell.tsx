"use client";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import clsx from "clsx";
import { LogOut, Sparkles, X } from "lucide-react";
import { auth } from "@/lib/api";
import { useErp } from "@/lib/erp";
import { LiveSurface } from "./a2ui/LiveSurface";

const NAV = [
  { href: "/agent", label: "Agent" },
  { href: "/dashboard", label: "Dashboard" },
  { href: "/m/customers", label: "Customers" },
  { href: "/m/invoices", label: "Invoices" },
  { href: "/m/orders", label: "Orders" },
  { href: "/m/products", label: "Inventory" },
  { href: "/m/expenses", label: "Expenses" },
  { href: "/m/employees", label: "Employees" },
  { href: "/reports", label: "Reports" },
];

export function LogoMark({ size = 32 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" fill="none" aria-label="NextERP">
      <defs>
        <linearGradient id="nx-g" x1="10" y1="10" x2="22" y2="22" gradientUnits="userSpaceOnUse">
          <stop stopColor="#a3e635" /><stop offset="1" stopColor="#16a34a" />
        </linearGradient>
      </defs>
      <rect width="32" height="32" rx="9" fill="#0c0d0c" />
      <path d="M10 22V10" stroke="#fff" strokeWidth="2.8" strokeLinecap="round" />
      <path d="M10 10l12 12" stroke="url(#nx-g)" strokeWidth="2.8" strokeLinecap="round" />
      <path d="M22 22V13" stroke="#fff" strokeWidth="2.8" strokeLinecap="round" />
      <path d="M19 12.5l3-3 3 3" stroke="#a3e635" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export function Logo() {
  return (
    <div className="flex items-center gap-2">
      <LogoMark />
      <span className="text-[15px] font-semibold tracking-tight">Next<span className="text-brand">ERP</span></span>
    </div>
  );
}

export function Shell({ children }: { children: React.ReactNode }) {
  const path = usePathname();
  const router = useRouter();
  const { user, live, drawer, setDrawer } = useErp();
  return (
    <div className="flex min-h-screen flex-col">
      <header className="sticky top-0 z-40 border-b border-line bg-white/85 backdrop-blur-xl">
        <div className="flex h-14 items-center gap-6 px-5">
          <div className="flex items-center gap-3">
            <Logo />
            <span className="hidden rounded-md border border-line px-1.5 py-0.5 text-[10px] font-medium text-muted lg:inline">{user?.company || "…"}</span>
          </div>
          <nav className="flex flex-1 items-center gap-0.5 overflow-x-auto scroll-thin">
            {NAV.map((n) => {
              const active = path === n.href || path.startsWith(n.href + "/");
              return (
                <Link key={n.href} href={n.href} className={clsx("relative whitespace-nowrap rounded-lg px-3 py-1.5 text-sm transition",
                  active ? "font-medium text-ink" : "text-muted hover:bg-canvas hover:text-ink")}>
                  {n.href === "/agent" && <Sparkles className="mr-1 inline h-3.5 w-3.5 text-brand" />}
                  {n.label}
                  {active && <span className="absolute inset-x-3 -bottom-[13px] h-[2px] rounded-full bg-ink" />}
                </Link>
              );
            })}
          </nav>
          <div className="flex items-center gap-3">
            <span className={clsx("flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[11px] font-medium", live ? "bg-brand-soft text-brand" : "bg-stone-100 text-muted")}>
              <span className={clsx("h-1.5 w-1.5 rounded-full", live ? "dot bg-brand" : "bg-faint")} />{live ? "Realtime" : "Offline"}
            </span>
            <div className="grid h-8 w-8 place-items-center rounded-full bg-gradient-to-br from-brand to-lime text-xs font-semibold text-white" title={user?.email}>
              {user?.name?.slice(0, 1) || "·"}
            </div>
            <button title="Sign out" onClick={() => { auth.clear(); router.replace("/login"); }} className="grid h-8 w-8 place-items-center rounded-lg text-muted hover:bg-canvas hover:text-ink">
              <LogOut className="h-4 w-4" />
            </button>
          </div>
        </div>
      </header>
      <main className="flex-1">{children}</main>

      {drawer && (
        <div className="fixed inset-0 z-50 flex justify-end">
          <div className="absolute inset-0 bg-ink/20 backdrop-blur-[2px]" onClick={() => setDrawer(null)} />
          <div className="rise relative m-3 flex w-full max-w-xl flex-col overflow-y-auto rounded-2xl bg-canvas p-3 shadow-2xl scroll-thin">
            <button onClick={() => setDrawer(null)} className="absolute right-5 top-5 z-10 grid h-8 w-8 place-items-center rounded-lg text-muted hover:bg-canvas hover:text-ink"><X className="h-4 w-4" /></button>
            <LiveSurface key={JSON.stringify(drawer).length + Math.random()} surfaceId="drawer" messages={drawer} onClose={() => setDrawer(null)} />
          </div>
        </div>
      )}
    </div>
  );
}

export function PageHeader({ title, sub, right }: { title: string; sub?: string; right?: React.ReactNode }) {
  return (
    <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
        {sub && <p className="mt-0.5 text-sm text-muted">{sub}</p>}
      </div>
      {right}
    </div>
  );
}
