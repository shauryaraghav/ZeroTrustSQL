import asyncio, hmac, json, logging, os, time
from contextlib import asynccontextmanager
import jwt
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, StreamingResponse
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.types import Command
from pydantic import BaseModel, Field
from . import cache, export
from .agent import build_graph, MAX_RETRIES
from .cache import r
from .policies import USERS

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger("audit")
SECRET = os.environ["JWT_SECRET"]


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with AsyncPostgresSaver.from_conn_string(os.environ["DATABASE_URL_ADMIN"]) as saver:
        await saver.setup()
        app.state.graph = build_graph(saver)
        asyncio.create_task(asyncio.to_thread(cache.model))  # warm the embedding model
        yield


app = FastAPI(title="Zero-Trust SQL Agent", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173"], allow_methods=["*"], allow_headers=["*"])


def current_user(authorization: str = Header(default="")):
    try:
        p = jwt.decode(authorization.removeprefix("Bearer "), SECRET, algorithms=["HS256"])
    except jwt.PyJWTError:
        raise HTTPException(401, "Invalid or expired token")
    return {"name": p["sub"], "role": p["role"]}


def admin_only(user=Depends(current_user)):
    if user["role"] != "admin":
        raise HTTPException(403, "Admins only")
    return user


class Login(BaseModel):
    username: str = Field(max_length=50)
    password: str = Field(max_length=100)


class Ask(BaseModel):
    question: str = Field(min_length=3, max_length=500)
    conversation_id: str = Field(min_length=8, max_length=64, pattern=r"^[\w-]+$")


class Decision(BaseModel):
    thread_id: str
    approve: bool


class Export(BaseModel):
    title: str = Field(max_length=200)
    summary: str = Field(default="", max_length=5000)
    columns: list[str] = Field(max_length=100)
    rows: list[list] = Field(max_length=5000)
    chart: dict | None = None


def sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


def sse_response(gen):
    return StreamingResponse(gen, media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.post("/api/login")
def login(b: Login):
    rec = USERS.get(b.username)
    if not rec or not hmac.compare_digest(rec[0], b.password):
        raise HTTPException(401, "Wrong username or password")
    token = jwt.encode({"sub": b.username, "role": rec[1], "exp": int(time.time()) + 8 * 3600}, SECRET, algorithm="HS256")
    return {"token": token, "name": b.username, "role": rec[1]}


async def run(inp, cfg, user, question):
    t0, final = time.time(), {}
    try:
        async for chunk in app.state.graph.astream(inp, cfg, stream_mode="updates"):
            if "__interrupt__" in chunk:
                v, tid = chunk["__interrupt__"][0].value, cfg["configurable"]["thread_id"]
                await r.set(f"pending:{tid}", json.dumps({"tid": tid, "user": user["name"], "question": question, **v}), ex=3600)
                yield sse("pending", {"thread_id": tid, "reason": v["reason"]})
                continue
            for node, upd in chunk.items():
                upd = upd or {}
                if node == "cache_lookup" and upd.get("cache_hit"):
                    yield sse("cache", {"similarity": upd["cache_sim"]})
                    yield sse("sql", {"sql": upd["sql"], "attempt": 1})
                elif node == "generate":
                    yield sse("sql", {"sql": upd["sql"], "attempt": upd["attempts"]})
                    yield sse("status", {"text": "Checking query with the SQL firewall"})
                elif node == "firewall" and not upd.get("error"):
                    yield sse("status", {"text": "Firewall passed"})
                elif node in ("firewall", "execute") and upd.get("error"):
                    yield sse("retry", {"error": upd["error"]})
                elif node == "execute":
                    final = upd
                    yield sse("result", {k: upd[k] for k in ("columns", "rows", "chart", "truncated")})
                    yield sse("status", {"text": "Writing summary"})
                elif node == "summarize":
                    yield sse("summary", {"text": upd["summary"]})
                elif node == "fail":
                    yield sse("fail", {"error": upd["fail_reason"]})
    except Exception:
        log.exception("agent crashed")
        yield sse("fail", {"error": "The agent hit an unexpected error. Try rephrasing the question."})
    log.info(json.dumps({"user": user["name"], "role": user["role"], "q": question, "ms": int((time.time() - t0) * 1000), "rows": len(final.get("rows", []))}))
    yield sse("done", {})


@app.post("/api/ask")
async def ask(b: Ask, user=Depends(current_user)):
    cfg = {"configurable": {"thread_id": f"{user['name']}:{b.conversation_id}"}}
    return sse_response(run({"question": b.question, "role": user["role"], "user": user["name"]}, cfg, user, b.question))


@app.post("/api/threads/{tid}/resume")
async def resume(tid: str, user=Depends(current_user)):
    raw = await r.get(f"pending:{tid}")
    if not raw or json.loads(raw)["user"] != user["name"]:
        raise HTTPException(404, "No pending approval")

    async def gen():
        d = None
        for _ in range(600):
            d = await r.get(f"decision:{tid}")
            if d:
                break
            await asyncio.sleep(1)
        if not d:
            yield sse("fail", {"error": "Approval timed out."})
            yield sse("done", {})
            return
        await r.delete(f"pending:{tid}", f"decision:{tid}")
        async for e in run(Command(resume={"approved": d == "approve"}), {"configurable": {"thread_id": tid}}, user, ""):
            yield e
    return sse_response(gen())


@app.get("/api/approvals")
async def approvals(_=Depends(admin_only)):
    out = []
    async for k in r.scan_iter("pending:*"):
        raw = await r.get(k)
        if raw:
            out.append(json.loads(raw))
    return out


@app.post("/api/approvals/decide")
async def decide(b: Decision, _=Depends(admin_only)):
    if not await r.exists(f"pending:{b.thread_id}"):
        raise HTTPException(404, "Nothing pending for that thread")
    await r.set(f"decision:{b.thread_id}", "approve" if b.approve else "reject", ex=3600)
    return {"ok": True}


FORMATS = {"csv": (export.to_csv, "text/csv"),
           "xlsx": (export.to_xlsx, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
           "pdf": (export.to_pdf, "application/pdf")}


@app.post("/api/export/{fmt}")
async def export_result(fmt: str, b: Export, _=Depends(current_user)):
    if fmt not in FORMATS:
        raise HTTPException(404, "Unknown format")
    fn, mime = FORMATS[fmt]
    data = await asyncio.to_thread(fn, b)
    return Response(data, media_type=mime, headers={"Content-Disposition": f'attachment; filename="query-result.{fmt}"'})


@app.get("/api/health")
def health():
    return {"ok": True}
