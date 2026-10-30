"""Resource registry: one definition drives REST CRUD, A2UI tables/forms and agent tools."""
from datetime import date, datetime
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from .models import Customer, Employee, Expense, Invoice, Order, Product


def F(key, label, type="text", required=False, options=None, list=True):
    return {"key": key, "label": label, "type": type, "required": required, "options": options or [], "list": list}


RESOURCES: dict[str, dict[str, Any]] = {
    "customers": {
        "model": Customer, "label": "Customers", "singular": "Customer", "icon": "users", "title": "name",
        "search": ["name", "email", "company", "city"], "status_options": ["active", "lead", "inactive"],
        "fields": [
            F("name", "Name", required=True), F("email", "Email", "email"), F("phone", "Phone", "phone"),
            F("company", "Company"), F("city", "City"),
            F("status", "Status", "select", options=["active", "lead", "inactive"]),
        ],
    },
    "products": {
        "model": Product, "label": "Products", "singular": "Product", "icon": "package", "title": "name",
        "search": ["name", "sku", "category"], "status_options": [],
        "fields": [
            F("sku", "SKU", required=True), F("name", "Name", required=True), F("category", "Category"),
            F("price", "Price", "money"), F("cost", "Cost", "money"), F("stock", "Stock", "number"),
            F("reorder_level", "Reorder level", "number", list=False),
        ],
    },
    "invoices": {
        "model": Invoice, "label": "Invoices", "singular": "Invoice", "icon": "receipt", "title": "number",
        "search": ["number", "notes"], "status_options": ["draft", "unpaid", "paid", "overdue"],
        "fields": [
            F("number", "Invoice #"), F("customer_id", "Customer", "ref:customers", required=True),
            F("issue_date", "Issue date", "date", required=True), F("due_date", "Due date", "date"),
            F("amount", "Amount", "money", required=True),
            F("status", "Status", "select", options=["draft", "unpaid", "paid", "overdue"]),
            F("notes", "Notes", "textarea", list=False),
        ],
    },
    "orders": {
        "model": Order, "label": "Sales Orders", "singular": "Order", "icon": "shopping-cart", "title": "number",
        "search": ["number"], "status_options": ["pending", "processing", "shipped", "delivered", "cancelled"],
        "fields": [
            F("number", "Order #"), F("customer_id", "Customer", "ref:customers", required=True),
            F("order_date", "Order date", "date", required=True), F("total", "Total", "money", required=True),
            F("status", "Status", "select", options=["pending", "processing", "shipped", "delivered", "cancelled"]),
        ],
    },
    "expenses": {
        "model": Expense, "label": "Expenses", "singular": "Expense", "icon": "wallet", "title": "vendor",
        "search": ["vendor", "category", "description"], "status_options": [],
        "fields": [
            F("date", "Date", "date", required=True),
            F("category", "Category", "select", required=True,
              options=["Salaries", "Rent", "Software", "Marketing", "Fuel", "Utilities", "Supplies", "Travel", "Maintenance"]),
            F("vendor", "Vendor"), F("amount", "Amount", "money", required=True),
            F("description", "Description", "textarea", list=False),
        ],
    },
    "employees": {
        "model": Employee, "label": "Employees", "singular": "Employee", "icon": "id-card", "title": "name",
        "search": ["name", "email", "role", "department"], "status_options": ["active", "on_leave", "terminated"],
        "fields": [
            F("name", "Name", required=True), F("email", "Email", "email"), F("role", "Role"),
            F("department", "Department", "select",
              options=["Operations", "Sales", "Finance", "Engineering", "Support", "HR", "Logistics"]),
            F("salary", "Salary", "money"), F("hire_date", "Hire date", "date"),
            F("status", "Status", "select", options=["active", "on_leave", "terminated"]),
        ],
    },
}

NUMBER_PREFIX = {"invoices": ("number", "INV-"), "orders": ("number", "SO-")}


def get_resource(name: str) -> dict:
    name = (name or "").lower().strip()
    if name not in RESOURCES:
        raise ValueError(f"Unknown resource '{name}'. Valid: {', '.join(RESOURCES)}")
    return RESOURCES[name]


def public_meta():
    return {
        k: {kk: vv for kk, vv in v.items() if kk != "model"}
        for k, v in RESOURCES.items()
    }


def serialize(resource: str, obj) -> dict:
    r = get_resource(resource)
    out = {"id": obj.id}
    for f in r["fields"]:
        v = getattr(obj, f["key"])
        if isinstance(v, (date, datetime)):
            v = v.isoformat()
        out[f["key"]] = v
        if f["type"].startswith("ref:") and hasattr(obj, "customer"):
            out["customer_name"] = obj.customer.name if obj.customer else None
    return out


def _coerce(ftype: str, v):
    if v is None or v == "":
        return None
    if ftype in ("money",):
        return round(float(v), 2)
    if ftype == "number":
        return int(float(v))
    if ftype.startswith("ref:"):
        return int(v)
    if ftype == "date":
        if isinstance(v, date):
            return v
        return date.fromisoformat(str(v)[:10])
    return str(v)


def apply_data(db: Session, resource: str, obj, data: dict):
    r = get_resource(resource)
    keys = {f["key"]: f for f in r["fields"]}
    for k, v in (data or {}).items():
        if k in keys:
            setattr(obj, k, _coerce(keys[k]["type"], v))
    # Agent-friendly: allow customer_name instead of customer_id
    if "customer_name" in (data or {}) and "customer_id" in keys and not data.get("customer_id"):
        c = db.scalar(select(Customer).where(func.lower(Customer.name).like(f"%{str(data['customer_name']).lower()}%")))
        if c:
            obj.customer_id = c.id


def _next_number(db: Session, resource: str) -> str:
    field, prefix = NUMBER_PREFIX[resource]
    model = get_resource(resource)["model"]
    count = db.scalar(select(func.max(model.id))) or 0
    return f"{prefix}{1001 + count}"


def create(db: Session, resource: str, data: dict):
    r = get_resource(resource)
    obj = r["model"]()
    apply_data(db, resource, obj, data)
    if resource in NUMBER_PREFIX and not getattr(obj, "number", None):
        obj.number = _next_number(db, resource)
    for f in r["fields"]:
        if f["required"] and getattr(obj, f["key"]) in (None, ""):
            if f["type"] == "date":
                setattr(obj, f["key"], date.today())
            else:
                raise ValueError(f"Field '{f['label']}' is required")
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


def update(db: Session, resource: str, id: int, data: dict):
    obj = get(db, resource, id)
    apply_data(db, resource, obj, data)
    db.commit()
    db.refresh(obj)
    return obj


def get(db: Session, resource: str, id: int):
    obj = db.get(get_resource(resource)["model"], int(id))
    if not obj:
        raise ValueError(f"{get_resource(resource)['singular']} #{id} not found")
    return obj


def delete(db: Session, resource: str, id: int):
    obj = get(db, resource, id)
    db.delete(obj)
    db.commit()


def query(db: Session, resource: str, filters: dict | None = None, search: str | None = None,
          sort_by: str | None = None, sort_dir: str = "desc", limit: int = 50, offset: int = 0):
    r = get_resource(resource)
    model = r["model"]
    stmt = select(model)
    cnt = select(func.count()).select_from(model)
    conds = []
    for k, v in (filters or {}).items():
        if v in (None, "", "all"):
            continue
        if k == "customer_name" and hasattr(model, "customer_id"):
            ids = select(Customer.id).where(func.lower(Customer.name).like(f"%{str(v).lower()}%"))
            conds.append(model.customer_id.in_(ids))
        elif k.endswith("_from") and hasattr(model, k[:-5]):
            conds.append(getattr(model, k[:-5]) >= _coerce("date", v) if "date" in k else getattr(model, k[:-5]) >= v)
        elif k.endswith("_to") and hasattr(model, k[:-3]):
            conds.append(getattr(model, k[:-3]) <= _coerce("date", v) if "date" in k else getattr(model, k[:-3]) <= v)
        elif k.endswith("_min") and hasattr(model, k[:-4]):
            conds.append(getattr(model, k[:-4]) >= float(v))
        elif k.endswith("_max") and hasattr(model, k[:-4]):
            conds.append(getattr(model, k[:-4]) <= float(v))
        elif hasattr(model, k):
            col = getattr(model, k)
            if isinstance(v, str):
                conds.append(func.lower(col) == v.lower())
            else:
                conds.append(col == v)
    if search:
        s = f"%{search.lower()}%"
        conds.append(or_(*[func.lower(getattr(model, f)).like(s) for f in r["search"]]))
    for c in conds:
        stmt = stmt.where(c)
        cnt = cnt.where(c)
    col = getattr(model, sort_by, None) if sort_by else None
    if col is None:
        date_field = next((f["key"] for f in r["fields"] if f["type"] == "date"), None)
        col = getattr(model, date_field) if date_field else model.id
    stmt = stmt.order_by(col.asc() if sort_dir == "asc" else col.desc(), model.id.desc())
    total = db.scalar(cnt) or 0
    rows = db.scalars(stmt.offset(offset).limit(min(int(limit or 50), 500))).unique().all()
    return [serialize(resource, o) for o in rows], total


def aggregate(db: Session, resource: str, group_by: str, metric: str | None = None, op: str = "sum",
              filters: dict | None = None):
    """Python-side aggregation keeps it DB-portable. group_by may be 'month:<date_field>'."""
    rows, _ = query(db, resource, filters=filters, limit=500)
    if len(rows) == 500:
        rows, _ = query(db, resource, filters=filters, limit=100000)
    groups: dict[str, list[float]] = {}
    for row in rows:
        if group_by.startswith("month:"):
            v = row.get(group_by[6:])
            key = v[:7] if v else "n/a"
        elif group_by == "customer_id":
            key = row.get("customer_name") or "n/a"
        else:
            key = str(row.get(group_by) or "n/a")
        groups.setdefault(key, []).append(float(row.get(metric) or 0) if metric else 1.0)
    out = []
    for k, vals in groups.items():
        if op == "count":
            val = len(vals)
        elif op == "avg":
            val = sum(vals) / len(vals) if vals else 0
        else:
            val = sum(vals)
        out.append({"label": k, "value": round(val, 2)})
    if group_by.startswith("month:"):
        out.sort(key=lambda x: x["label"])
    else:
        out.sort(key=lambda x: -x["value"])
    return out
