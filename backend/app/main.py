import asyncio
import json
from datetime import datetime

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import resources as R
from . import seed
from .agent import run_agent
from .auth import current_user, make_token, user_from_token, verify_password
from .config import FRONTEND_ORIGIN, OPENROUTER_MODEL
from .db import SessionLocal, get_db
from .events import data_changed, subscribe, unsubscribe
from .models import Conversation, Message, User
from .screens import build_screen, handle_action

app = FastAPI(title="NextERP Agentic ERP")
app.add_middleware(CORSMiddleware, allow_origins=[FRONTEND_ORIGIN, "http://127.0.0.1:3000"], allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])


@app.on_event("startup")
def _startup():
    seed.run()


def _err(e: Exception):
    raise HTTPException(400, str(e))


# ------------------------------------------------------------------ auth
class LoginIn(BaseModel):
    email: str
    password: str


def _user_out(u: User):
    return {"id": u.id, "email": u.email, "name": u.name, "company": u.company, "role": u.role}


@app.post("/api/auth/login")
def login(body: LoginIn, db: Session = Depends(get_db)):
    u = db.scalar(select(User).where(User.email == body.email.lower().strip()))
    if not u or not verify_password(body.password, u.password_hash):
        raise HTTPException(401, "Invalid email or password")
    return {"token": make_token(u), "user": _user_out(u)}


@app.get("/api/auth/me")
def me(user: User = Depends(current_user)):
    return {**_user_out(user), "model": OPENROUTER_MODEL}


# ------------------------------------------------------------------ meta + REST CRUD
@app.get("/api/meta/resources")
def meta(user: User = Depends(current_user)):
    return R.public_meta()


@app.get("/api/data/{resource}")
def list_records(resource: str, search: str | None = None, limit: int = 50, offset: int = 0,
                 user: User = Depends(current_user), db: Session = Depends(get_db)):
    try:
        rows, total = R.query(db, resource, None, search, limit=limit, offset=offset)
    except ValueError as e:
        _err(e)
    return {"rows": rows, "total": total}


@app.post("/api/data/{resource}")
def create_record(resource: str, data: dict, user: User = Depends(current_user), db: Session = Depends(get_db)):
    try:
        obj = R.create(db, resource, data)
    except ValueError as e:
        _err(e)
    data_changed(resource, "created", obj.id)
    return R.serialize(resource, obj)


@app.put("/api/data/{resource}/{id}")
def update_record(resource: str, id: int, data: dict, user: User = Depends(current_user), db: Session = Depends(get_db)):
    try:
        obj = R.update(db, resource, id, data)
    except ValueError as e:
        _err(e)
    data_changed(resource, "updated", id)
    return R.serialize(resource, obj)


@app.delete("/api/data/{resource}/{id}")
def delete_record(resource: str, id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    try:
        R.delete(db, resource, id)
    except ValueError as e:
        _err(e)
    data_changed(resource, "deleted", id)
    return {"ok": True}


# ------------------------------------------------------------------ A2UI
@app.get("/api/a2ui/screen")
def a2ui_screen(name: str, surfaceId: str, params: str = "{}", user: User = Depends(current_user),
                db: Session = Depends(get_db)):
    try:
        return {"messages": build_screen(db, name, surfaceId, json.loads(params or "{}"))}
    except ValueError as e:
        _err(e)


class ActionIn(BaseModel):
    userAction: dict


@app.post("/api/a2ui/action")
def a2ui_action(body: ActionIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    ua = body.userAction
    try:
        return handle_action(db, ua.get("surfaceId", ""), ua.get("name", ""), ua.get("context") or {})
    except (ValueError, KeyError) as e:
        db.rollback()
        _err(e)


# ------------------------------------------------------------------ realtime events (SSE)
@app.get("/api/events")
async def events(request: Request, token: str):
    db = SessionLocal()
    try:
        user_from_token(db, token)
    finally:
        db.close()
    q = subscribe()

    async def gen():
        try:
            yield "event: ready\ndata: {}\n\n"
            while True:
                if await request.is_disconnected():
                    break
                try:
                    msg = await asyncio.wait_for(q.get(), timeout=15)
                    yield f"data: {msg}\n\n"
                except asyncio.TimeoutError:
                    yield ": ping\n\n"
        finally:
            unsubscribe(q)

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# ------------------------------------------------------------------ conversations + agent chat
@app.get("/api/conversations")
def conversations(user: User = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.scalars(select(Conversation).where(Conversation.user_id == user.id)
                      .order_by(Conversation.updated_at.desc())).all()
    return [{"id": c.id, "title": c.title, "updated_at": c.updated_at.isoformat()} for c in rows]


def _own_conv(db, user, cid) -> Conversation:
    c = db.get(Conversation, cid)
    if not c or c.user_id != user.id:
        raise HTTPException(404, "Conversation not found")
    return c


@app.get("/api/conversations/{cid}")
def conversation(cid: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    c = _own_conv(db, user, cid)
    msgs = db.scalars(select(Message).where(Message.conversation_id == cid).order_by(Message.id)).all()
    return {"id": c.id, "title": c.title,
            "messages": [{"id": m.id, "role": m.role, "content": m.content, "parts": m.parts or []} for m in msgs]}


@app.delete("/api/conversations/{cid}")
def delete_conversation(cid: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    db.delete(_own_conv(db, user, cid))
    db.commit()
    return {"ok": True}


class ChatIn(BaseModel):
    message: str
    conversation_id: int | None = None


@app.post("/api/chat")
async def chat(body: ChatIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if body.conversation_id:
        conv = _own_conv(db, user, body.conversation_id)
    else:
        conv = Conversation(user_id=user.id, title=body.message.strip()[:60] or "New chat")
        db.add(conv)
        db.commit()
    prior = db.scalars(select(Message).where(Message.conversation_id == conv.id).order_by(Message.id.desc()).limit(16)).all()
    history = []
    for m in reversed(prior):
        text = m.content
        surfaces = [p for p in (m.parts or []) if p.get("t") == "surface"]
        if m.role == "assistant" and surfaces:
            text += "\n[UI shown: " + ", ".join(p.get("spec", {}).get("screen", "custom") for p in surfaces) + "]"
        history.append({"role": m.role, "content": text or "(ui)"})
    history.append({"role": "user", "content": body.message})
    db.add(Message(conversation_id=conv.id, role="user", content=body.message, parts=[]))
    conv.updated_at = datetime.utcnow()
    db.commit()

    async def gen():
        yield f"data: {json.dumps({'type': 'conversation', 'id': conv.id, 'title': conv.title})}\n\n"
        text, parts = "", []
        try:
            async for ev in run_agent(db, user, history):
                if ev["type"] == "token":
                    text += ev["text"]
                    if parts and parts[-1]["t"] == "text":
                        parts[-1]["text"] += ev["text"]
                    else:
                        parts.append({"t": "text", "text": ev["text"]})
                elif ev["type"] == "tool_start":
                    parts.append({"t": "tool", "id": ev["id"], "name": ev["name"], "label": ev["label"], "status": "running"})
                elif ev["type"] == "tool_end":
                    for p in parts:
                        if p.get("t") == "tool" and p.get("id") == ev["id"]:
                            p["status"] = "done" if ev["ok"] else "error"
                elif ev["type"] == "surface":
                    parts.append(ev["part"])
                yield f"data: {json.dumps(ev, default=str)}\n\n"
        except Exception as e:  # noqa: BLE001
            msg = f"\n\n⚠️ Agent error: {e}"
            text += msg
            parts.append({"t": "text", "text": msg})
            yield f"data: {json.dumps({'type': 'token', 'text': msg})}\n\n"
        db.add(Message(conversation_id=conv.id, role="assistant", content=text, parts=parts))
        db.commit()
        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
