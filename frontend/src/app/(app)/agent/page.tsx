"use client";
import { Suspense } from "react";
import { Chat } from "@/components/chat/Chat";

export default function AgentPage() {
  return <Suspense><Chat /></Suspense>;
}
