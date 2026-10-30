"use client";
import { use } from "react";
import { LiveSurface } from "@/components/a2ui/LiveSurface";

export default function ResourcePage({ params }: { params: Promise<{ resource: string }> }) {
  const { resource } = use(params);
  return (
    <div className="mx-auto max-w-[1440px] p-6">
      <LiveSurface key={resource} surfaceId={`screen-${resource}`} spec={{ screen: "list", params: { resource, limit: 100 } }} />
    </div>
  );
}
