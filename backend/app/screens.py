"""Server-driven A2UI screens. Both the traditional UI and the agent render through these builders."""
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import resources as R
from .a2ui import Surface, delete_surface, lit, path
from .events import data_changed
from .models import Customer, Employee, Expense, Invoice, Order, Product

STATUS_TONE = {"paid": "success", "active": "success", "delivered": "success", "unpaid": "warning", "pending": "warning",
               "processing": "info", "shipped": "info", "lead": "info", "on_leave": "warning", "draft": "neutral",
               "overdue": "danger", "cancelled": "danger", "inactive": "neutral", "terminated": "danger"}

EDIT = {"name": "open_form", "label": "Edit", "icon": "pencil"}
DELETE = {"name": "delete_record", "label": "Delete", "icon": "trash", "tone": "danger", "confirm": True}
MARK_PAID = {"name": "mark_paid", "label": "Mark paid", "icon": "check", "when": {"status": ["unpaid", "overdue", "draft"]}}


def _months(n: int = 12) -> list[str]:
    d = date.today().replace(day=1)
    out = []
    for _ in range(n):
        out.append(d.strftime("%Y-%m"))
        d = (d - timedelta(days=1)).replace(day=1)
    return list(reversed(out))


def _label(m: str) -> str:
    return date.fromisoformat(m + "-01").strftime("%b")


def monthly_financials(db: Session, n: int = 12) -> list[dict]:
    months = _months(n)
    rev = {m: 0.0 for m in months}
    cost = {m: 0.0 for m in months}
    for inv in db.scalars(select(Invoice)).unique():
        m = inv.issue_date.strftime("%Y-%m")
        if m in rev and inv.status != "draft":
            rev[m] += inv.amount
    for e in db.scalars(select(Expense)):
        m = e.date.strftime("%Y-%m")
        if m in cost:
            cost[m] += e.amount
    return [{"label": _label(m), "month": m, "revenue": round(rev[m], 2), "costs": round(cost[m], 2),
             "profit": round(rev[m] - cost[m], 2)} for m in months]


def _columns(resource: str, compact: bool = False) -> list[dict]:
    r = R.get_resource(resource)
    cols = []
    for f in r["fields"]:
        if not f["list"]:
            continue
        if f["type"].startswith("ref:"):
            cols.append({"key": "customer_name", "label": f["label"], "type": "avatar"})
        else:
            t = "badge" if f["key"] == "status" else f["type"]
            cols.append({"key": f["key"], "label": f["label"], "type": t})
    if compact:
        cols = cols[:5]
    return cols


def _table(s: Surface, resource: str, rows: list, compact=False, **kw) -> str:
    actions = [EDIT, DELETE]
    if resource == "invoices":
        actions = [MARK_PAID, EDIT, DELETE]
    return s.table(resource, _columns(resource, compact), rows, actions, statusTones=STATUS_TONE, compact=compact, **kw)


def _summary(db: Session, s: Surface, resource: str) -> list[str]:
    today = date.today()
    if resource == "invoices":
        invs = db.scalars(select(Invoice)).unique().all()
        tot = lambda st: sum(i.amount for i in invs if i.status == st)
        return [s.metric("Paid", tot("paid"), fmt="money", tone="success"),
                s.metric("Unpaid", tot("unpaid"), fmt="money", tone="warning"),
                s.metric("Overdue", tot("overdue"), fmt="money", tone="danger"),
                s.metric("Invoices", len(invs))]
    if resource == "products":
        ps = db.scalars(select(Product)).all()
        return [s.metric("SKUs", len(ps)), s.metric("Units in stock", sum(p.stock for p in ps)),
                s.metric("Inventory value", sum(p.stock * p.cost for p in ps), fmt="money"),
                s.metric("Low stock", sum(1 for p in ps if p.stock <= p.reorder_level), tone="danger")]
    if resource == "customers":
        cs = db.scalars(select(Customer)).all()
        return [s.metric("Customers", len(cs)), s.metric("Active", sum(c.status == "active" for c in cs), tone="success"),
                s.metric("Leads", sum(c.status == "lead" for c in cs), tone="info"),
                s.metric("Inactive", sum(c.status == "inactive" for c in cs))]
    if resource == "orders":
        os_ = db.scalars(select(Order)).unique().all()
        open_ = [o for o in os_ if o.status in ("pending", "processing", "shipped")]
        return [s.metric("Orders", len(os_)), s.metric("Open", len(open_), tone="warning"),
                s.metric("Open value", sum(o.total for o in open_), fmt="money"),
                s.metric("Delivered", sum(o.status == "delivered" for o in os_), tone="success")]
    if resource == "expenses":
        es = db.scalars(select(Expense)).all()
        this_m = [e for e in es if e.date.strftime("%Y-%m") == today.strftime("%Y-%m")]
        return [s.metric("This month", sum(e.amount for e in this_m), fmt="money"),
                s.metric("Last 12 months", sum(e.amount for e in es), fmt="money"),
                s.metric("Entries", len(es)),
                s.metric("Avg / entry", (sum(e.amount for e in es) / len(es)) if es else 0, fmt="money")]
    if resource == "employees":
        em = db.scalars(select(Employee)).all()
        act = [e for e in em if e.status == "active"]
        return [s.metric("Headcount", len(act)), s.metric("On leave", sum(e.status == "on_leave" for e in em), tone="warning"),
                s.metric("Annual payroll", sum(e.salary for e in act), fmt="money"),
                s.metric("Departments", len({e.department for e in em}))]
    return []


# ---------------------------------------------------------------- screens

def screen_dashboard(db: Session, sid: str, params: dict) -> list[dict]:
    s = Surface(sid)
    fin = monthly_financials(db)
    invs = db.scalars(select(Invoice)).unique().all()
    revenue = sum(f["revenue"] for f in fin)
    costs = sum(f["costs"] for f in fin)
    last, prev = fin[-1], fin[-2]
    pct = lambda a, b: round((a - b) / b * 100, 1) if b else None
    outstanding = sum(i.amount for i in invs if i.status in ("unpaid", "overdue"))
    paid = sum(i.amount for i in invs if i.status == "paid")
    unpaid = sum(i.amount for i in invs if i.status == "unpaid")
    overdue = sum(i.amount for i in invs if i.status == "overdue")

    kpis = s.add("Grid", {"children": {"explicitList": [
        s.metric("Revenue (12m)", revenue, delta=pct(last["revenue"], prev["revenue"]), fmt="money",
                 spark=[f["revenue"] for f in fin], sub="vs last month"),
        s.metric("Costs (12m)", costs, delta=pct(last["costs"], prev["costs"]), fmt="money", invertDelta=True,
                 spark=[f["costs"] for f in fin], tone="danger", sub="vs last month"),
        s.metric("Net profit (12m)", revenue - costs, delta=pct(last["profit"], prev["profit"]), fmt="money",
                 spark=[f["profit"] for f in fin], sub="vs last month"),
        s.metric("Outstanding", outstanding, fmt="money", sub=f"{sum(i.status == 'overdue' for i in invs)} overdue invoices",
                 tone="warning"),
    ]}, "columns": 4})

    chart = s.card(s.column([
        s.row([s.text("Revenue and costs", "h3"), s.add("Spacer", {}),
               s.button("Ask agent", "client:ask_agent", {"prompt": "Analyze my revenue and costs trend for the last 12 months and suggest improvements"},
                        variant="ghost", icon="sparkles")]),
        s.chart("line", fin, [{"key": "revenue", "label": "Revenue", "color": "green"},
                              {"key": "costs", "label": "Costs", "color": "red"},
                              {"key": "profit", "label": "Net profit", "color": "black"}], height=280),
    ]))

    def inv_rows(st):
        rows, _ = R.query(db, "invoices", {"status": st} if st else None, limit=7)
        return _table(s, "invoices", rows, compact=True)

    invoices = s.card(s.column([
        s.row([s.text("Invoices", "h3"), s.add("Spacer", {}),
               s.button("New invoice", "open_form", {"resource": "invoices"}, variant="secondary", icon="plus")]),
        s.segments([{"label": "Paid", "value": paid, "tone": "success"},
                    {"label": "Unpaid", "value": unpaid, "tone": "warning"},
                    {"label": "Overdue", "value": overdue, "tone": "danger"}]),
        s.tabs([("Unpaid", inv_rows("unpaid")), ("Overdue", inv_rows("overdue")), ("Paid", inv_rows("paid")),
                ("All", inv_rows(None))]),
    ]))

    cats = R.aggregate(db, "expenses", "category", "amount", "sum")
    total_c = sum(c["value"] for c in cats) or 1
    for c in cats:
        c["share"] = round(c["value"] / total_c * 100, 1)
    costs_card = s.card(s.column([
        s.text("Costs by category", "h3"),
        s.add("BarList", {"items": cats, "format": "money"}),
    ]))

    pipeline = R.aggregate(db, "orders", "status", None, "count")
    orders_card = s.card(s.column([
        s.text("Sales order pipeline", "h3"),
        s.chart("donut", pipeline, [{"key": "value", "label": "Orders"}], height=220),
    ]))

    low, _ = R.query(db, "products", None, sort_by="stock", sort_dir="asc", limit=6)
    low = [p for p in low if p["stock"] <= p["reorder_level"]]
    stock_card = s.card(s.column([
        s.row([s.text("Low stock alerts", "h3"), s.add("Spacer", {}), s.badge(f"{len(low)} items", "danger")]),
        _table(s, "products", low, compact=True) if low else s.text("All products are above reorder level.", "caption"),
    ]))

    root = s.column([
        kpis,
        s.add("Grid", {"children": {"explicitList": [chart, invoices]}, "columns": 2}),
        s.add("Grid", {"children": {"explicitList": [costs_card, orders_card, stock_card]}, "columns": 3}),
    ], gap="lg")
    return s.messages(root)


def screen_list(db: Session, sid: str, params: dict) -> list[dict]:
    resource = params.get("resource", "customers")
    r = R.get_resource(resource)
    filters = dict(params.get("filters") or {})
    q = filters.pop("q", None) or params.get("search")
    status = filters.get("status")
    limit = int(params.get("limit") or 50)
    rows, total = R.query(db, resource, filters, q, params.get("sort_by"), params.get("sort_dir", "desc"), limit)
    compact = bool(params.get("compact"))
    s = Surface(sid)
    s.data = {"filters": {"q": q or "", "status": status or "all"}}
    title = params.get("title") or r["label"]

    children = []
    header = [s.column([s.text(title, "h2"), s.text(f"{total} records" + (f" · showing {len(rows)}" if total > len(rows) else ""), "caption")], gap="xs"),
              s.add("Spacer", {}),
              s.button(f"New {r['singular'].lower()}", "open_form", {"resource": resource}, icon="plus")]
    children.append(s.row(header))
    if not compact:
        summ = _summary(db, s, resource)
        if summ:
            children.append(s.add("Grid", {"children": {"explicitList": summ}, "columns": 4}))
        fctx = {"screen": "list", "resource": resource, "filters": path("/filters")}
        bar = [s.add("TextField", {"label": lit(""), "text": path("/filters/q"), "textFieldType": "search",
                                   "placeholder": f"Search {r['label'].lower()}…",
                                   "onSubmit": {"name": "apply_filter", "context": [{"key": k, "value": v if isinstance(v, dict) else lit(v)} for k, v in fctx.items()]}})]
        if r["status_options"]:
            bar.append(s.add("MultipleChoice", {
                "label": lit(""), "selections": path("/filters/status"), "maxAllowedSelections": 1, "variant": "chips",
                "options": [{"label": lit("All"), "value": "all"}] + [{"label": lit(o.replace("_", " ").title()), "value": o} for o in r["status_options"]],
                "onChange": {"name": "apply_filter", "context": [{"key": k, "value": v if isinstance(v, dict) else lit(v)} for k, v in fctx.items()]},
            }))
        children.append(s.row(bar, distribution="spaceBetween"))
    children.append(s.card(_table(s, resource, rows, compact=compact), padding="none"))
    return s.messages(s.column(children, gap="lg"))


def screen_form(db: Session, sid: str, params: dict) -> list[dict]:
    resource = params["resource"]
    r = R.get_resource(resource)
    rid = params.get("id")
    values = R.serialize(resource, R.get(db, resource, rid)) if rid else {}
    for k, v in (params.get("prefill") or {}).items():
        values[k] = v
    s = Surface(sid)
    form = {}
    fields = []
    for f in r["fields"]:
        if resource in R.NUMBER_PREFIX and f["key"] == "number" and not rid:
            continue
        p = f"/form/{f['key']}"
        v = values.get(f["key"])
        label = f["label"] + (" *" if f["required"] else "")
        if f["type"] == "select":
            fields.append(s.choice(label, p, f["options"]))
            v = v or (f["options"][0] if f["options"] else "")
        elif f["type"].startswith("ref:"):
            custs = db.scalars(select(Customer).order_by(Customer.name)).all()
            fields.append(s.choice(label, p, [{"label": c.name, "value": str(c.id)} for c in custs], variant="combobox"))
            if not v and values.get("customer_name"):
                m = next((c for c in custs if values["customer_name"].lower() in c.name.lower()), None)
                v = m.id if m else None
        else:
            ft = {"money": "number", "number": "number", "date": "date", "textarea": "longText",
                  "email": "email"}.get(f["type"], "shortText")
            fields.append(s.text_field(label, p, ft))
            if f["type"] == "date" and not v and f["required"]:
                v = date.today().isoformat()
        form[f["key"]] = "" if v is None else (str(v) if not isinstance(v, (int, float)) or f["type"].startswith("ref:") else v)
    s.data = {"form": form}
    title = f"{'Edit' if rid else 'New'} {r['singular'].lower()}" + (f" · {values.get(r['title'])}" if rid else "")
    root = s.card(s.column([
        s.row([s.icon(r["icon"]), s.column([s.text(title, "h3"),
               s.text("Changes sync instantly to every open screen.", "caption")], gap="xs")]),
        s.add("Grid", {"children": {"explicitList": fields}, "columns": 2}),
        s.row([s.add("Spacer", {}),
               s.button("Cancel", "close_surface", {}, variant="ghost"),
               s.button("Save" if rid else "Create", "save_record",
                        {"resource": resource, "id": rid or "", "data": path("/form")}, icon="check")]),
    ], gap="lg"))
    return s.messages(root)


def screen_chart(db: Session, sid: str, params: dict) -> list[dict]:
    s = Surface(sid)
    resource = params.get("resource")
    title = params.get("title") or "Chart"
    ctype = params.get("chart_type", "bar")
    if resource == "financials" or not resource:
        data = monthly_financials(db, int(params.get("months") or 12))
        series = [{"key": "revenue", "label": "Revenue", "color": "green"}, {"key": "costs", "label": "Costs", "color": "red"},
                  {"key": "profit", "label": "Net profit", "color": "black"}]
    else:
        group_by = params.get("group_by", "status")
        data = R.aggregate(db, resource, group_by, params.get("metric"), params.get("op", "sum"), params.get("filters"))
        if not group_by.startswith("month:"):
            data = data[: int(params.get("top") or 12)]
        else:
            for d in data:
                d["label"] = _label(d["label"]) + " " + d["label"][2:4] if d["label"] != "n/a" else d["label"]
        series = [{"key": "value", "label": params.get("metric_label") or (params.get("metric") or "count").title()}]
    fmt = "money" if params.get("metric") in ("amount", "total", "price", "salary") or resource == "financials" else "number"
    total = sum(d.get("value", d.get("revenue", 0)) for d in data)
    root = s.card(s.column([
        s.row([s.text(title, "h3"), s.add("Spacer", {}), s.badge(f"Total {total:,.0f}" if fmt == "number" else f"Total ${total:,.0f}", "neutral")]),
        s.chart(ctype, data, series, height=300, format=fmt),
    ]))
    return s.messages(root)


def screen_record(db: Session, sid: str, params: dict) -> list[dict]:
    resource = params["resource"]
    r = R.get_resource(resource)
    row = R.serialize(resource, R.get(db, resource, params["id"]))
    s = Surface(sid)
    items = []
    for f in r["fields"]:
        key = "customer_name" if f["type"].startswith("ref:") else f["key"]
        items.append({"label": f["label"], "value": row.get(key), "type": "badge" if key == "status" else f["type"]})
    root = s.card(s.column([
        s.row([s.icon(r["icon"]), s.text(f"{r['singular']} · {row.get(r['title'])}", "h3"), s.add("Spacer", {}),
               s.button("Edit", "open_form", {"resource": resource, "id": row["id"]}, variant="secondary", icon="pencil")]),
        s.add("KeyValue", {"items": items, "statusTones": STATUS_TONE}),
    ]))
    return s.messages(root)


def screen_reports(db: Session, sid: str, params: dict) -> list[dict]:
    s = Surface(sid)
    fin = monthly_financials(db)
    rev = sum(f["revenue"] for f in fin)
    cost = sum(f["costs"] for f in fin)
    margin = (rev - cost) / rev * 100 if rev else 0
    by_cust = R.aggregate(db, "invoices", "customer_id", "amount", "sum")[:10]
    by_cat = R.aggregate(db, "expenses", "category", "amount", "sum")
    by_dept = R.aggregate(db, "employees", "department", "salary", "sum")
    pl_rows = [{"id": i, "month": f["month"], "revenue": f["revenue"], "costs": f["costs"], "profit": f["profit"],
                "margin": round(f["profit"] / f["revenue"] * 100, 1) if f["revenue"] else 0} for i, f in enumerate(fin)]
    root = s.column([
        s.row([s.column([s.text("Reports", "h2"), s.text("Profit & loss, sales and cost analytics — last 12 months", "caption")], gap="xs"),
               s.add("Spacer", {}),
               s.button("Ask agent for insights", "client:ask_agent",
                        {"prompt": "Give me an executive summary of business performance with key risks and opportunities"}, icon="sparkles")]),
        s.add("Grid", {"children": {"explicitList": [
            s.metric("Revenue", rev, fmt="money"), s.metric("Costs", cost, fmt="money", tone="danger"),
            s.metric("Net profit", rev - cost, fmt="money"), s.metric("Net margin", margin, fmt="percent")]}, "columns": 4}),
        s.add("Grid", {"children": {"explicitList": [
            s.card(s.column([s.text("Profit & loss trend", "h3"),
                             s.chart("bar", fin, [{"key": "revenue", "label": "Revenue", "color": "green"},
                                                  {"key": "costs", "label": "Costs", "color": "red"}], height=280, format="money")])),
            s.card(s.column([s.text("Top customers by billing", "h3"),
                             s.chart("hbar", by_cust, [{"key": "value", "label": "Billed"}], height=280, format="money")])),
        ]}, "columns": 2}),
        s.add("Grid", {"children": {"explicitList": [
            s.card(s.column([s.text("Expense mix", "h3"), s.chart("donut", by_cat, [{"key": "value", "label": "Spend"}], height=240, format="money")])),
            s.card(s.column([s.text("Payroll by department", "h3"), s.chart("pie", by_dept, [{"key": "value", "label": "Payroll"}], height=240, format="money")])),
        ]}, "columns": 2}),
        s.card(s.column([s.text("Monthly P&L statement", "h3"),
                         s.table(None, [{"key": "month", "label": "Month"}, {"key": "revenue", "label": "Revenue", "type": "money"},
                                        {"key": "costs", "label": "Costs", "type": "money"},
                                        {"key": "profit", "label": "Net profit", "type": "money"},
                                        {"key": "margin", "label": "Margin %", "type": "percent"}], list(reversed(pl_rows)))])),
    ], gap="lg")
    return s.messages(root)


def screen_success(sid: str, title: str, body: str, resource: str | None = None, id: int | None = None) -> list[dict]:
    s = Surface(sid)
    kids = [s.row([s.icon("check-circle"), s.column([s.text(title, "h4"), s.text(body, "caption")], gap="xs")])]
    if resource and id:
        kids.append(s.row([s.button("View", "show_record", {"resource": resource, "id": id}, variant="secondary"),
                           s.button("Edit", "open_form", {"resource": resource, "id": id}, variant="ghost")]))
    return s.messages(s.card(s.column(kids), tone="success"))


SCREENS = {"dashboard": screen_dashboard, "list": screen_list, "form": screen_form, "chart": screen_chart,
           "record": screen_record, "reports": screen_reports}


def build_screen(db: Session, name: str, sid: str, params: dict | None = None) -> list[dict]:
    fn = SCREENS.get(name)
    if not fn:
        raise ValueError(f"Unknown screen {name}")
    return fn(db, sid, params or {})


# ---------------------------------------------------------------- actions

def handle_action(db: Session, sid: str, name: str, ctx: dict) -> dict:
    """Process an A2UI userAction and return follow-up A2UI messages."""
    if name == "apply_filter":
        params = {"resource": ctx.get("resource"), "filters": ctx.get("filters") or {}}
        return {"messages": build_screen(db, ctx.get("screen", "list"), sid, params), "params": params}
    if name in ("refresh", "navigate"):
        params = ctx.get("params") or {}
        return {"messages": build_screen(db, ctx.get("screen"), sid, params), "params": params}
    if name == "open_form":
        p = {"resource": ctx["resource"], "id": ctx.get("id") or None, "prefill": ctx.get("prefill")}
        return {"messages": build_screen(db, "form", "drawer", p), "target": "drawer"}
    if name == "show_record":
        p = {"resource": ctx["resource"], "id": ctx["id"]}
        return {"messages": build_screen(db, "record", "drawer", p), "target": "drawer"}
    if name == "close_surface":
        return {"messages": delete_surface(sid)}
    if name == "save_record":
        resource, rid, data = ctx["resource"], ctx.get("id"), ctx.get("data") or {}
        r = R.get_resource(resource)
        if rid:
            obj = R.update(db, resource, int(rid), data)
            verb = "updated"
        else:
            obj = R.create(db, resource, data)
            verb = "created"
        data_changed(resource, verb, obj.id)
        label = getattr(obj, r["title"], None) or f"#{obj.id}"
        toast = f"{r['singular']} {label} {verb}"
        if sid == "drawer":
            return {"messages": delete_surface(sid), "toast": toast}
        return {"messages": screen_success(sid, toast, "Saved and synced to all screens in realtime.", resource, obj.id),
                "toast": toast, "params": None, "freeze": True}
    if name == "delete_record":
        resource, rid = ctx["resource"], int(ctx["id"])
        R.delete(db, resource, rid)
        data_changed(resource, "deleted", rid)
        return {"messages": [], "toast": f"{R.get_resource(resource)['singular']} deleted"}
    if name == "mark_paid":
        obj = R.update(db, "invoices", int(ctx["id"]), {"status": "paid"})
        data_changed("invoices", "updated", obj.id)
        return {"messages": [], "toast": f"Invoice {obj.number} marked as paid"}
    raise ValueError(f"Unknown action '{name}'")
