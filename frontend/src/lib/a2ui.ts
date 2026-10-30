/**
 * Minimal Google A2UI (v0.8) client runtime: applies server->client messages
 * (surfaceUpdate, dataModelUpdate, beginRendering, deleteSurface) into a renderable surface.
 */
export type A2Component = { id: string; component: Record<string, any> };
export type A2Message =
  | { surfaceUpdate: { surfaceId: string; components: A2Component[] } }
  | { dataModelUpdate: { surfaceId: string; path?: string; contents: any[] } }
  | { beginRendering: { surfaceId: string; root: string } }
  | { deleteSurface: { surfaceId: string } };

export type SurfaceState = {
  id: string;
  root: string | null;
  components: Record<string, A2Component>;
  data: Record<string, any>;
  deleted?: boolean;
};

export type UserAction = { name: string; surfaceId: string; sourceComponentId?: string; timestamp: string; context: Record<string, any> };

export function contentsToObject(contents: any[]): Record<string, any> {
  const out: Record<string, any> = {};
  for (const c of contents || []) {
    if ("valueMap" in c) out[c.key] = contentsToObject(c.valueMap);
    else if ("valueNumber" in c) out[c.key] = c.valueNumber;
    else if ("valueBoolean" in c) out[c.key] = c.valueBoolean;
    else out[c.key] = c.valueString ?? "";
  }
  return out;
}

export function getPath(obj: any, path: string) {
  const parts = path.split("/").filter(Boolean);
  let cur = obj;
  for (const p of parts) { if (cur == null) return undefined; cur = cur[p]; }
  return cur;
}

export function setPath(obj: any, path: string, value: any): any {
  const parts = path.split("/").filter(Boolean);
  if (!parts.length) return value;
  const clone = Array.isArray(obj) ? [...obj] : { ...(obj || {}) };
  const [head, ...rest] = parts;
  clone[head] = rest.length ? setPath(clone[head], "/" + rest.join("/"), value) : value;
  return clone;
}

export function applyMessages(prev: SurfaceState | null, msgs: A2Message[], surfaceId: string): SurfaceState | null {
  let s: SurfaceState | null = prev ? { ...prev, components: { ...prev.components } } : null;
  let fresh = false;
  for (const m of msgs) {
    if ("surfaceUpdate" in m) {
      if (m.surfaceUpdate.surfaceId !== surfaceId) continue;
      if (!s || !fresh) { s = { id: surfaceId, root: s?.root ?? null, components: {}, data: s?.data ?? {} }; fresh = true; }
      for (const c of m.surfaceUpdate.components) s.components[c.id] = c;
    } else if ("dataModelUpdate" in m) {
      if (m.dataModelUpdate.surfaceId !== surfaceId) continue;
      s = s || { id: surfaceId, root: null, components: {}, data: {} };
      const obj = contentsToObject(m.dataModelUpdate.contents);
      const p = m.dataModelUpdate.path || "/";
      s.data = p === "/" ? obj : setPath(s.data, p, obj);
    } else if ("beginRendering" in m) {
      if (m.beginRendering.surfaceId !== surfaceId) continue;
      s = s || { id: surfaceId, root: null, components: {}, data: {} };
      s.root = m.beginRendering.root;
    } else if ("deleteSurface" in m) {
      if (m.deleteSurface.surfaceId !== surfaceId) continue;
      s = s ? { ...s, deleted: true } : { id: surfaceId, root: null, components: {}, data: {}, deleted: true };
    }
  }
  return s;
}

/** Resolve an A2UI BoundValue ({literalString}|{path}|...) against the data model. */
export function resolve(v: any, data: any): any {
  if (v == null || typeof v !== "object" || Array.isArray(v)) return v;
  if ("path" in v) {
    const got = getPath(data, v.path);
    return got !== undefined ? got : v.literalString ?? v.literalNumber ?? v.literalBoolean;
  }
  if ("literalString" in v) return v.literalString;
  if ("literalNumber" in v) return v.literalNumber;
  if ("literalBoolean" in v) return v.literalBoolean;
  return v;
}

export function resolveContext(ctx: { key: string; value: any }[] | undefined, data: any, extra: Record<string, any> = {}) {
  const out: Record<string, any> = {};
  for (const c of ctx || []) out[c.key] = resolve(c.value, data);
  return { ...out, ...extra };
}
