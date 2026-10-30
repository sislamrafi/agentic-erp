"""Helpers for producing Google A2UI (v0.8) server-to-client messages.

Standard catalog components are used for layout and inputs (Column, Row, Card, Text, Button,
TextField, MultipleChoice, Divider, Icon, Tabs). Business visuals use a custom catalog
(Metric, Chart, DataTable, Badge, ProgressSegments, Alert), which A2UI explicitly allows.
"""
from typing import Any


def lit(v: Any) -> dict:
    if isinstance(v, bool):
        return {"literalBoolean": v}
    if isinstance(v, (int, float)):
        return {"literalNumber": v}
    return {"literalString": "" if v is None else str(v)}


def path(p: str) -> dict:
    return {"path": p}


def to_contents(d: dict) -> list:
    out = []
    for k, v in d.items():
        if isinstance(v, bool):
            out.append({"key": k, "valueBoolean": v})
        elif isinstance(v, (int, float)):
            out.append({"key": k, "valueNumber": v})
        elif isinstance(v, dict):
            out.append({"key": k, "valueMap": to_contents(v)})
        else:
            out.append({"key": k, "valueString": "" if v is None else str(v)})
    return out


class Surface:
    def __init__(self, surface_id: str):
        self.sid = surface_id
        self.components: list[dict] = []
        self.data: dict = {}
        self._n = 0

    def _id(self, prefix: str) -> str:
        self._n += 1
        return f"{prefix}-{self._n}"

    def add(self, ctype: str, props: dict, id: str | None = None) -> str:
        cid = id or self._id(ctype.lower())
        self.components.append({"id": cid, "component": {ctype: props}})
        return cid

    # ---- standard catalog ----
    def text(self, s, hint: str = "body", **kw) -> str:
        return self.add("Text", {"text": lit(s) if not isinstance(s, dict) else s, "usageHint": hint, **kw})

    def column(self, children: list[str], gap: str = "md", **kw) -> str:
        return self.add("Column", {"children": {"explicitList": children}, "gap": gap, **kw})

    def row(self, children: list[str], gap: str = "md", distribution: str = "start", alignment: str = "center", **kw) -> str:
        return self.add("Row", {"children": {"explicitList": children}, "gap": gap,
                                "distribution": distribution, "alignment": alignment, **kw})

    def card(self, child: str, **kw) -> str:
        return self.add("Card", {"child": child, **kw})

    def divider(self) -> str:
        return self.add("Divider", {})

    def icon(self, name: str) -> str:
        return self.add("Icon", {"name": lit(name)})

    def button(self, label: str, action: str, context: dict | None = None, variant: str = "primary", icon: str | None = None) -> str:
        child = self.text(label, "label")
        ctx = [{"key": k, "value": v if isinstance(v, dict) and ("path" in v or any(x.startswith("literal") for x in v)) else lit(v)}
               for k, v in (context or {}).items()]
        props = {"child": child, "action": {"name": action, "context": ctx}, "primary": variant == "primary", "variant": variant}
        if icon:
            props["icon"] = icon
        return self.add("Button", props)

    def text_field(self, label: str, data_path: str, ftype: str = "shortText", placeholder: str = "") -> str:
        return self.add("TextField", {"label": lit(label), "text": path(data_path), "textFieldType": ftype,
                                      "placeholder": placeholder})

    def choice(self, label: str, data_path: str, options: list, variant: str = "select") -> str:
        opts = [{"label": lit(o["label"] if isinstance(o, dict) else str(o).replace("_", " ").title()),
                 "value": o["value"] if isinstance(o, dict) else str(o)} for o in options]
        return self.add("MultipleChoice", {"label": lit(label), "selections": path(data_path), "options": opts,
                                           "maxAllowedSelections": 1, "variant": variant})

    def tabs(self, items: list[tuple[str, str]]) -> str:
        return self.add("Tabs", {"tabItems": [{"title": lit(t), "child": c} for t, c in items]})

    # ---- custom catalog ----
    def metric(self, label, value, delta=None, trend=None, sub=None, spark=None, fmt="number", **kw) -> str:
        return self.add("Metric", {"label": label, "value": value, "delta": delta, "trend": trend, "sub": sub,
                                   "spark": spark, "format": fmt, **kw})

    def chart(self, chart_type: str, data: list, series: list, title: str | None = None, x: str = "label", **kw) -> str:
        return self.add("Chart", {"chartType": chart_type, "data": data, "series": series, "title": title, "xKey": x, **kw})

    def table(self, resource: str | None, columns: list, rows: list, actions: list | None = None, **kw) -> str:
        return self.add("DataTable", {"resource": resource, "columns": columns, "rows": rows,
                                      "rowActions": actions or [], **kw})

    def badge(self, label: str, tone: str = "neutral") -> str:
        return self.add("Badge", {"label": label, "tone": tone})

    def segments(self, items: list) -> str:
        return self.add("ProgressSegments", {"items": items})

    def alert(self, title: str, body: str = "", tone: str = "info") -> str:
        return self.add("Alert", {"title": title, "body": body, "tone": tone})

    def messages(self, root: str) -> list[dict]:
        msgs = [{"surfaceUpdate": {"surfaceId": self.sid, "components": self.components}}]
        if self.data:
            msgs.append({"dataModelUpdate": {"surfaceId": self.sid, "path": "/", "contents": to_contents(self.data)}})
        msgs.append({"beginRendering": {"surfaceId": self.sid, "root": root}})
        return msgs


def delete_surface(sid: str) -> list[dict]:
    return [{"deleteSurface": {"surfaceId": sid}}]


CATALOG = ["Column", "Row", "Grid", "Card", "Text", "Button", "TextField", "MultipleChoice", "Tabs", "List", "CheckBox",
           "Divider", "Icon", "Image", "Spacer", "Metric", "Chart", "DataTable", "Badge", "Alert", "ProgressSegments",
           "BarList", "KeyValue"]
_CANON = {c.lower(): c for c in CATALOG}


def _canon(name) -> str | None:
    return _CANON.get(str(name).replace("_", "").replace("-", "").lower())


def normalize_components(comps: list, root: str | None) -> tuple[list, str]:
    """Repair common LLM mistakes in free-form A2UI so it always renders:
    wrapper keys ({"Type": {"metric": ...}}), flat {"type": ...} items, lowercase names, missing root."""
    out = []
    for c in comps:
        if not isinstance(c, dict) or "id" not in c:
            continue
        if "component" not in c and "type" in c:
            name, props = c["type"], {k: v for k, v in c.items() if k not in ("id", "type", "props")} | (c.get("props") or {})
        else:
            comp = c.get("component") or {}
            if not isinstance(comp, dict) or not comp:
                continue
            name, props = next(iter(comp.items()))
            if not _canon(name) and isinstance(props, dict) and len(props) == 1:
                name, props = next(iter(props.items()))
        canon = _canon(name)
        if not canon or not isinstance(props, dict):
            continue
        out.append({"id": str(c["id"]), "component": {canon: props}})
    kinds = {c["id"]: next(iter(c["component"])) for c in out}
    for c in out:
        row = c["component"].get("Row")
        kids = (row or {}).get("children", {}).get("explicitList") or []
        if row and kids and all(kinds.get(k) == "Metric" for k in kids):
            c["component"] = {"Grid": {"children": {"explicitList": kids}, "columns": min(4, len(kids))}}
    ids = set(kinds)
    if root not in ids:
        referenced = set()
        for c in out:
            props = next(iter(c["component"].values()))
            referenced.update((props.get("children") or {}).get("explicitList") or [])
            if props.get("child"):
                referenced.add(props["child"])
        tops = [c["id"] for c in out if c["id"] not in referenced]
        root = "auto-root"
        out.append({"id": root, "component": {"Column": {"children": {"explicitList": tops}, "gap": "lg"}}})
    return out, root
