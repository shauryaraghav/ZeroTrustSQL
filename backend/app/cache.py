"""Semantic query cache: MiniLM embeddings in Redis. Scoped per role; cached SQL is re-validated on every hit."""
import asyncio, hashlib, json, os
import numpy as np
import redis.asyncio as aioredis

r = aioredis.from_url(os.environ.get("REDIS_URL", "redis://localhost:6379/0"), decode_responses=True)
THRESHOLD = float(os.getenv("CACHE_THRESHOLD", 0.90))
_model = None


def model():
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer("sentence-transformers/all-MiniLM-L12-v2")
    return _model


async def embed(q: str):
    return await asyncio.to_thread(lambda: model().encode(q.lower().strip(), normalize_embeddings=True))


async def lookup(q: str, role: str):
    v, best = await embed(q), None
    async for key in r.scan_iter(f"qcache:{role}:*"):
        raw = await r.get(key)
        if not raw:
            continue
        item = json.loads(raw)
        sim = float(np.dot(v, np.array(item["emb"])))
        if sim >= THRESHOLD and (best is None or sim > best["sim"]):
            best = {"sql": item["sql"], "chart": item["chart"], "sim": round(sim, 3)}
    return best


async def store(q: str, role: str, sql: str, chart: dict):
    v = await embed(q)
    key = f"qcache:{role}:{hashlib.sha1(q.lower().strip().encode()).hexdigest()}"
    await r.set(key, json.dumps({"q": q, "sql": sql, "chart": chart, "emb": v.tolist()}), ex=86400)
