"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import clsx from "clsx";
import { api } from "@/lib/api";
import { applyMessages, setPath, type A2Message, type SurfaceState } from "@/lib/a2ui";
import { useErp } from "@/lib/erp";
import { A2Renderer } from "./Renderer";

export type SurfaceSpec = { screen: string; params?: any; live?: boolean };

/**
 * Hosts one A2UI surface. Either fetches a server-driven screen (spec) or renders inline
 * messages. Live surfaces re-render in realtime whenever the backend publishes a data change.
 */
export function LiveSurface({ surfaceId, spec, messages, onClose, className }:
  { surfaceId: string; spec?: SurfaceSpec; messages?: A2Message[]; onClose?: () => void; className?: string }) {
  const { onData, sendAction } = useErp();
  const [surface, setSurface] = useState<SurfaceState | null>(() => (messages ? applyMessages(null, messages, surfaceId) : null));
  const [params, setParams] = useState<any>(spec?.params || {});
  const [frozen, setFrozen] = useState(false);
  const [flash, setFlash] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const timer = useRef<any>(null);
  const specKey = spec ? spec.screen : null;

  useEffect(() => { if (messages) setSurface(applyMessages(null, messages, surfaceId)); }, [messages, surfaceId]);

  const load = useCallback(async (p: any, quiet = false) => {
    if (!specKey) return;
    try {
      const res = await api<{ messages: A2Message[] }>(`/api/a2ui/screen?name=${specKey}&surfaceId=${surfaceId}&params=${encodeURIComponent(JSON.stringify(p || {}))}`);
      setSurface((prev) => {
        const next = applyMessages(null, res.messages, surfaceId);
        // keep in-progress filter text when refreshing quietly
        if (quiet && prev?.data?.filters && next) next.data = { ...next.data, filters: prev.data.filters };
        return next;
      });
      setError(null);
      if (quiet) { setFlash(true); setTimeout(() => setFlash(false), 900); }
    } catch (e: any) { setError(e.message); }
  }, [specKey, surfaceId]);

  useEffect(() => { if (specKey) load(params); /* eslint-disable-next-line react-hooks/exhaustive-deps */ }, [specKey]);

  useEffect(() => {
    if (!spec || spec.live === false || frozen) return;
    return onData(() => {
      clearTimeout(timer.current);
      timer.current = setTimeout(() => load(params, true), 250);
    });
  }, [spec, frozen, params, onData, load]);

  const setData = useCallback((path: string, value: any) => {
    setSurface((s) => (s ? { ...s, data: setPath(s.data, path, value) } : s));
  }, []);

  const dispatch = useCallback(async (name: string, context: Record<string, any>, sourceId?: string) => {
    const res = await sendAction({ name, surfaceId, sourceComponentId: sourceId, timestamp: new Date().toISOString(), context });
    if (!res) return;
    if (res.freeze) setFrozen(true);
    if (res.params) setParams((p: any) => ({ ...p, ...res.params }));
    if (res.messages?.length) {
      const closed = res.messages.some((m: any) => m.deleteSurface?.surfaceId === surfaceId);
      if (closed) { onClose ? onClose() : setSurface((s) => (s ? { ...s, deleted: true } : s)); return; }
      setSurface((prev) => applyMessages(prev, res.messages, surfaceId));
    }
  }, [sendAction, surfaceId, onClose]);

  if (error) return <div className="card p-4 text-sm text-danger">Failed to render surface: {error}</div>;
  if (surface?.deleted) return <div className="text-xs text-faint">Surface closed.</div>;
  if (messages && !surface?.root) {
    return <div className="card p-4 text-sm text-muted">This UI could not be rendered (no valid root component).</div>;
  }
  if (!surface?.root) {
    return <div className={clsx("flex flex-col gap-3", className)}><div className="skeleton h-24" /><div className="skeleton h-48" /></div>;
  }
  return (
    <div className={clsx("relative transition", flash && "[&_.card]:ring-2 [&_.card]:ring-lime/50", className)}>
      <A2Renderer surface={surface} setData={setData} dispatch={dispatch} />
    </div>
  );
}
