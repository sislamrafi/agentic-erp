"use client";
import { LiveSurface } from "@/components/a2ui/LiveSurface";

export default function Reports() {
  return (
    <div className="mx-auto max-w-[1440px] p-6">
      <LiveSurface surfaceId="screen-reports" spec={{ screen: "reports" }} />
    </div>
  );
}
