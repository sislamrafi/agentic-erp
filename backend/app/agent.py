"""ERP agent: OpenRouter tool-calling loop that streams text, tool activity and A2UI surfaces."""
import json
import uuid
from datetime import date
from typing import AsyncIterator

import httpx
from sqlalchemy.orm import Session

from . import resources as R
from .a2ui import Surface, normalize_components
from .config import OPENROUTER_API_KEY, OPENROUTER_BASE_URL, OPENROUTER_MODEL
from .events import data_changed
from .models import User
from .screens import monthly_financials

RES_ENUM = list(R.RESOURCES)


def _tool(name, desc, props, required=()):
    return {"type": "function", "function": {"name": name, "description": desc,
            "parameters": {"type": "object", "properties": props, "required": list(required)}}}


RES = {"type": "string", "enum": RES_ENUM}
TOOLS = [
    _tool("query_records", "Search/filter records to READ data for reasoning. Filters are exact field matches; also supports "
          "<field>_from/_to for dates, <field>_min/_max for numbers, and customer_name (fuzzy).",
          {"resource": RES, "filters": {"type": "object"}, "search": {"type": "string"},
           "sort_by": {"type": "string"}, "sort_dir": {"type": "string", "enum": ["asc", "desc"]},
           "limit": {"type": "integer"}}, ["resource"]),
    _tool("aggregate", "Group and aggregate a resource. group_by is a field name, 'customer_id', or 'month:<date_field>'.",
          {"resource": RES, "group_by": {"type": "string"}, "metric": {"type": "string"},
           "op": {"type": "string", "enum": ["sum", "count", "avg"]}, "filters": {"type": "object"}},
          ["resource", "group_by"]),
    _tool("business_summary", "Get headline KPIs: revenue, costs, profit, outstanding invoices, low stock, headcount.", {}),
    _tool("create_record", "Create a record. For invoices/orders you may pass customer_name instead of customer_id.",
          {"resource": RES, "data": {"type": "object"}}, ["resource", "data"]),
    _tool("update_record", "Update fields of a record by id.",
          {"resource": RES, "id": {"type": "integer"}, "data": {"type": "object"}}, ["resource", "id", "data"]),
    _tool("delete_record", "Delete a record by id. Only call after the user explicitly confirmed the deletion.",
          {"resource": RES, "id": {"type": "integer"}}, ["resource", "id"]),
    _tool("show_table", "Render a LIVE interactive A2UI table (with edit/delete/search) in the chat.",
          {"resource": RES, "filters": {"type": "object"}, "search": {"type": "string"}, "title": {"type": "string"},
           "limit": {"type": "integer"}, "sort_by": {"type": "string"}, "sort_dir": {"type": "string"}}, ["resource"]),
    _tool("show_form", "Render an A2UI add/edit form in the chat. Use for adding records when the user wants to fill or review "
          "details; pass prefill with what you know. Pass id to edit.",
          {"resource": RES, "id": {"type": "integer"}, "prefill": {"type": "object"}}, ["resource"]),
    _tool("show_record", "Render a detail card for a single record.", {"resource": RES, "id": {"type": "integer"}},
          ["resource", "id"]),
    _tool("show_chart", "Render a LIVE A2UI chart. resource='financials' gives monthly revenue/costs/profit. Otherwise "
          "aggregates resource by group_by (field, customer_id, or month:<date_field>) with metric+op.",
          {"title": {"type": "string"}, "chart_type": {"type": "string", "enum": ["bar", "hbar", "line", "area", "pie", "donut"]},
           "resource": {"type": "string", "enum": RES_ENUM + ["financials"]}, "group_by": {"type": "string"},
           "metric": {"type": "string"}, "op": {"type": "string", "enum": ["sum", "count", "avg"]},
           "filters": {"type": "object"}}, ["title", "chart_type", "resource"]),
    _tool("show_dashboard", "Render the full live business dashboard (KPIs, revenue chart, invoices, costs, stock).", {}),
    _tool("show_reports", "Render the full P&L / analytics report.", {}),
    _tool("render_ui", "Render a custom A2UI surface for anything the other show_* tools can't express (risk reports, "
          "KPI boards, comparisons, checklists). components is a flat A2UI v0.8 list; each item is "
          "{\"id\": \"...\", \"component\": {\"<ComponentName>\": {props}}} where <ComponentName> is one of: "
          "Column/Row/Grid {children:{explicitList:[ids]}, columns(Grid only)}, Card {child:id}, "
          "Text {text:{literalString:'...'}, usageHint:h2|h3|h4|body|caption}, "
          "Metric {label, value:number, format:money|number|percent, delta, tone:success|warning|danger|info}, "
          "Badge {label, tone}, Alert {title, body, tone}, Chart {chartType:bar|line|pie|donut, data:[{label,value}], "
          "series:[{key:'value',label}]}, DataTable {columns:[{key,label,type}], rows:[...]}, "
          "Button {child:textId, action:{name:'client:ask_agent', context:[{key:'prompt',value:{literalString:'...'}}]}}. "
          "Example: [{\"id\":\"root\",\"component\":{\"Column\":{\"children\":{\"explicitList\":[\"t\",\"g\"]}}}},"
          "{\"id\":\"t\",\"component\":{\"Text\":{\"text\":{\"literalString\":\"Report\"},\"usageHint\":\"h2\"}}},"
          "{\"id\":\"g\",\"component\":{\"Grid\":{\"columns\":2,\"children\":{\"explicitList\":[\"m1\"]}}}},"
          "{\"id\":\"m1\",\"component\":{\"Metric\":{\"label\":\"Overdue\",\"value\":7950,\"format\":\"money\"}}}]",
          {"components": {"type": "array", "items": {"type": "object"}}, "root": {"type": "string"}}, ["components", "root"]),
]


def system_prompt(user: User) -> str:
    schema = []
    for k, r in R.RESOURCES.items():
        fields = ", ".join(f"{f['key']}({f['type']}{':' + '|'.join(f['options']) if f['options'] else ''})" for f in r["fields"])
        schema.append(f"- {k}: {fields}")
    return f"""You are NextERP Agent, the autonomous AI operator of an ERP for small & medium businesses.
Company: {user.company}. User: {user.name}. Today: {date.today().isoformat()}. Currency: USD.

Data model:
{chr(10).join(schema)}

How you work:
- You are agentic: plan, call tools, chain several tools, and finish the job instead of asking unnecessary questions.
- The user sees rich generative UI (Google A2UI). Whenever the user wants to SEE data (list, report, chart, dashboard, a record),
  call a show_* tool so they get a live interactive surface. Use query_records/aggregate/business_summary for your own reasoning.
- To add data: if you have the required fields, call create_record then show_record so the user sees it. If key info is missing
  or the user says "add/create" vaguely, call show_form with a sensible prefill.
- To edit: update_record (find the id first with query_records). To delete: confirm with the user first, then delete_record.
- After tools return, reply with a short, sharp summary in markdown (bold key numbers, bullet insights). Never dump raw JSON
  or repeat entire tables in text — the UI already shows them.
- Be proactive: point out overdue invoices, low stock, cost spikes when relevant."""


def _summary(db: Session) -> dict:
    fin = monthly_financials(db)
    invs, _ = R.query(db, "invoices", limit=100000)
    prods, _ = R.query(db, "products", limit=100000)
    emps, _ = R.query(db, "employees", {"status": "active"}, limit=100000)
    return {
        "revenue_12m": round(sum(f["revenue"] for f in fin), 2), "costs_12m": round(sum(f["costs"] for f in fin), 2),
        "profit_12m": round(sum(f["profit"] for f in fin), 2), "this_month": fin[-1], "last_month": fin[-2],
        "unpaid_total": round(sum(i["amount"] for i in invs if i["status"] == "unpaid"), 2),
        "overdue_total": round(sum(i["amount"] for i in invs if i["status"] == "overdue"), 2),
        "overdue_count": sum(i["status"] == "overdue" for i in invs),
        "low_stock": [p["name"] for p in prods if p["stock"] <= p["reorder_level"]],
        "headcount": len(emps),
    }


def _surface(spec: dict) -> dict:
    return {"t": "surface", "id": uuid.uuid4().hex[:10], "spec": spec}


def run_tool(db: Session, name: str, args: dict) -> tuple[str, dict | None]:
    """Execute a tool, returning (result text for the LLM, optional UI part)."""
    if name == "query_records":
        rows, total = R.query(db, args["resource"], args.get("filters"), args.get("search"), args.get("sort_by"),
                              args.get("sort_dir", "desc"), args.get("limit") or 25)
        return json.dumps({"total": total, "rows": rows}, default=str), None
    if name == "aggregate":
        return json.dumps(R.aggregate(db, args["resource"], args["group_by"], args.get("metric"), args.get("op", "sum"),
                                      args.get("filters"))), None
    if name == "business_summary":
        return json.dumps(_summary(db)), None
    if name == "create_record":
        obj = R.create(db, args["resource"], args.get("data") or {})
        data_changed(args["resource"], "created", obj.id, "agent")
        return json.dumps({"created": R.serialize(args["resource"], obj)}, default=str), \
            _surface({"screen": "record", "params": {"resource": args["resource"], "id": obj.id}})
    if name == "update_record":
        obj = R.update(db, args["resource"], args["id"], args.get("data") or {})
        data_changed(args["resource"], "updated", obj.id, "agent")
        return json.dumps({"updated": R.serialize(args["resource"], obj)}, default=str), \
            _surface({"screen": "record", "params": {"resource": args["resource"], "id": obj.id}})
    if name == "delete_record":
        R.delete(db, args["resource"], args["id"])
        data_changed(args["resource"], "deleted", args["id"], "agent")
        return json.dumps({"deleted": args["id"]}), None
    if name == "show_table":
        params = {"resource": args["resource"], "filters": args.get("filters") or {}, "search": args.get("search"),
                  "title": args.get("title"), "limit": args.get("limit") or 25, "sort_by": args.get("sort_by"),
                  "sort_dir": args.get("sort_dir") or "desc", "compact": True}
        rows, total = R.query(db, args["resource"], params["filters"], params["search"], params["sort_by"],
                              params["sort_dir"], 10)
        return json.dumps({"shown_to_user": True, "total": total, "sample": rows[:10]}, default=str), \
            _surface({"screen": "list", "params": params})
    if name == "show_form":
        if args.get("id"):
            R.get(db, args["resource"], args["id"])
        return "Form displayed to the user. They will fill and submit it.", \
            _surface({"screen": "form", "params": {"resource": args["resource"], "id": args.get("id"),
                                                   "prefill": args.get("prefill") or {}}, "live": False})
    if name == "show_record":
        row = R.serialize(args["resource"], R.get(db, args["resource"], args["id"]))
        return json.dumps(row, default=str), _surface({"screen": "record", "params": args})
    if name == "show_chart":
        p = {k: v for k, v in args.items()}
        from .screens import screen_chart
        msgs = screen_chart(db, "probe", p)
        data = next(c["component"]["Chart"]["data"] for m in msgs if "surfaceUpdate" in m
                    for c in m["surfaceUpdate"]["components"] if "Chart" in c["component"])
        return json.dumps({"shown_to_user": True, "data": data[:24]}), _surface({"screen": "chart", "params": p})
    if name == "show_dashboard":
        return json.dumps({"shown_to_user": True, **_summary(db)}, default=str), _surface({"screen": "dashboard", "params": {}})
    if name == "show_reports":
        return json.dumps({"shown_to_user": True, **_summary(db)}, default=str), _surface({"screen": "reports", "params": {}})
    if name == "render_ui":
        comps, root = normalize_components(args.get("components") or [], args.get("root"))
        sid = "agent-" + uuid.uuid4().hex[:8]
        msgs = [{"surfaceUpdate": {"surfaceId": sid, "components": comps}}, {"beginRendering": {"surfaceId": sid, "root": root}}]
        return "Rendered.", {"t": "surface", "id": sid, "messages": msgs}
    raise ValueError(f"Unknown tool {name}")


TOOL_LABELS = {"query_records": "Querying records", "aggregate": "Crunching numbers", "business_summary": "Reading KPIs",
               "create_record": "Creating record", "update_record": "Updating record", "delete_record": "Deleting record",
               "show_table": "Building table", "show_form": "Building form", "show_record": "Rendering record",
               "show_chart": "Drawing chart", "show_dashboard": "Composing dashboard", "show_reports": "Generating report",
               "render_ui": "Designing UI"}


async def _stream_completion(messages: list) -> AsyncIterator[dict]:
    headers = {"Authorization": f"Bearer {OPENROUTER_API_KEY}", "HTTP-Referer": "http://localhost:3000",
               "X-Title": "NextERP Agentic ERP", "Content-Type": "application/json"}
    body = {"model": OPENROUTER_MODEL, "messages": messages, "tools": TOOLS, "tool_choice": "auto", "stream": True,
            "temperature": 0.3}
    async with httpx.AsyncClient(timeout=httpx.Timeout(120, connect=15)) as client:
        async with client.stream("POST", f"{OPENROUTER_BASE_URL}/chat/completions", json=body, headers=headers) as resp:
            if resp.status_code >= 400:
                txt = (await resp.aread()).decode(errors="ignore")
                raise RuntimeError(f"OpenRouter error {resp.status_code}: {txt[:400]}")
            async for line in resp.aiter_lines():
                if not line.startswith("data:"):
                    continue
                payload = line[5:].strip()
                if payload == "[DONE]":
                    break
                try:
                    chunk = json.loads(payload)
                except json.JSONDecodeError:
                    continue
                if "error" in chunk:
                    raise RuntimeError(chunk["error"].get("message", str(chunk["error"])))
                yield chunk


async def run_agent(db: Session, user: User, history: list[dict]) -> AsyncIterator[dict]:
    """Yields UI events: token, reasoning, tool_start, tool_end, surface, error."""
    if not OPENROUTER_API_KEY:
        yield {"type": "token", "text": "⚠️ **OPENROUTER_API_KEY** is not set in `backend/.env`. Add it and restart the backend."}
        return
    messages = [{"role": "system", "content": system_prompt(user)}] + history
    for _step in range(8):
        content, calls = "", {}
        async for chunk in _stream_completion(messages):
            choice = (chunk.get("choices") or [{}])[0]
            delta = choice.get("delta") or {}
            if delta.get("reasoning"):
                yield {"type": "reasoning", "text": delta["reasoning"]}
            if delta.get("content"):
                content += delta["content"]
                yield {"type": "token", "text": delta["content"]}
            for tc in delta.get("tool_calls") or []:
                slot = calls.setdefault(tc.get("index", 0), {"id": "", "name": "", "args": ""})
                if tc.get("id"):
                    slot["id"] = tc["id"]
                fn = tc.get("function") or {}
                if fn.get("name"):
                    slot["name"] += fn["name"]
                if fn.get("arguments"):
                    slot["args"] += fn["arguments"]
        if not calls:
            return
        ordered = [calls[i] for i in sorted(calls)]
        for c in ordered:
            c["id"] = c["id"] or "call_" + uuid.uuid4().hex[:8]
        messages.append({"role": "assistant", "content": content or None, "tool_calls": [
            {"id": c["id"], "type": "function", "function": {"name": c["name"], "arguments": c["args"] or "{}"}} for c in ordered]})
        for c in ordered:
            try:
                args = json.loads(c["args"] or "{}")
            except json.JSONDecodeError:
                args = {}
            yield {"type": "tool_start", "id": c["id"], "name": c["name"], "label": TOOL_LABELS.get(c["name"], c["name"]), "args": args}
            try:
                result, part = run_tool(db, c["name"], args)
                ok = True
            except Exception as e:  # noqa: BLE001 - surface any tool error back to the model
                db.rollback()
                result, part, ok = json.dumps({"error": str(e)}), None, False
            yield {"type": "tool_end", "id": c["id"], "name": c["name"], "ok": ok}
            if part:
                yield {"type": "surface", "part": part}
            messages.append({"role": "tool", "tool_call_id": c["id"], "content": result[:12000]})
    yield {"type": "token", "text": "\n\n_(Stopped after several steps.)_"}
