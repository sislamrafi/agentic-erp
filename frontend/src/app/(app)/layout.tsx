"use client";
import { ErpProvider } from "@/lib/erp";
import { Shell } from "@/components/Shell";

export default function AppLayout({ children }: { children: React.ReactNode }) {
  return <ErpProvider><Shell>{children}</Shell></ErpProvider>;
}
