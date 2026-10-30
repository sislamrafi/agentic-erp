"use client";
import { Sparkles } from "lucide-react";
import { LiveSurface } from "@/components/a2ui/LiveSurface";
import { PageHeader } from "@/components/Shell";
import { useErp } from "@/lib/erp";

export default function Dashboard() {
  const { user, askAgent } = useErp();
  return (
    <div className="mx-auto max-w-[1440px] p-6">
      <PageHeader title={`Good day${user ? ", " + user.name.split(" ")[0] : ""}`} sub="Last 12 months · every widget is an A2UI surface that updates in realtime"
        right={<button onClick={() => askAgent("Give me today's briefing: what needs my attention right now?")}
          className="inline-flex h-9 items-center gap-2 rounded-xl bg-ink px-4 text-sm font-medium text-white hover:bg-ink/85">
          <Sparkles className="h-4 w-4 text-lime" />Daily briefing</button>} />
      <LiveSurface surfaceId="screen-dashboard" spec={{ screen: "dashboard" }} />
    </div>
  );
}
