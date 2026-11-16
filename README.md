# Zero-Trust SQL & BI Agent

Natural language -> read-only SQL -> self-correcting execution -> streamed chart + summary.

## Run
```
cp .env.example .env   # add OPENAI_API_KEY
docker compose up --build
```
UI: http://localhost:5173 · API: http://localhost:8000/docs

## Run notes
Fresh DB needed after upgrading: `docker compose down -v` first. First start downloads the MiniLM model (cached in a volume). Backend image is large (CPU torch).
Demo logins: admin/admin123, analyst/analyst123, junior/junior123.

## Features
- **Semantic cache**: MiniLM-L12-v2 embeddings in Redis, per role, cosine >= `CACHE_THRESHOLD`; cached SQL still goes through the firewall. Lookup is a linear scan (fine for thousands of entries; use RediSearch/pgvector beyond that). Follow-ups are never cached.
- **EXPLAIN advisor**: queries slower than `EXPLAIN_MS` get `EXPLAIN ANALYZE`; findings (seq scans with heavy filtering, disk sorts, big nested loops) are appended to the summary. Set `EXPLAIN_MS=0` to see it on the demo data.
- **RBAC**: JWT login, per-role table and column policy in `policies.py`, enforced in the firewall; the model only sees the schema its role may use. `junior` cannot touch `customers.email/phone` or `employees`; `analyst` cannot touch `employees`. Restricted columns are blocked, not partially masked.
- **HITL**: non-admin queries with a cross join or planner cost above `APPROVAL_COST` pause the graph (`AsyncPostgresSaver`); admins approve or reject in the UI. Try: "pair every order with every order item".
- **Multi-turn**: conversation history lives in the checkpointed graph state (last 4 turns).
- **Export**: CSV, XLSX (with native chart), PDF (summary, chart, table). CSV/XLSX cells are guarded against formula injection.
- **Chart toolbar**: bar/line/scatter/pie and swap axes; exports follow the current view.

## Security layers (any one failing still leaves the others)
1. `sqlglot` AST firewall (`backend/app/guard.py`): single SELECT only, blocks DML/DDL/COPY/SET/INTO, writable CTEs, dangerous functions (`pg_sleep`, `pg_read_file`, ...), non-public schemas, tables outside the introspected allowlist; injects `LIMIT`.
2. DB role `bi_readonly`: SELECT-only grants, `default_transaction_read_only=on`, 5s `statement_timeout`, connection limit.
3. Row cap (`MAX_ROWS`), 500-char question cap, prompt tells the model the question is data.
4. JSON audit log per query (question, latency, row count); internals never leak to the client.

## Flow (LangGraph)
introspect -> generate -> firewall -> execute -> summarize, with firewall/execute errors routed back to generate up to `MAX_RETRIES`, then a `fail` node.
SSE events: status, sql, retry, result, summary, fail, done. Summary arrives as one event, not token-by-token.

## Extras added beyond the spec
Seeded demo shop DB, schema cache (5 min TTL), per-attempt SQL + error viewer, row-limit notice, example prompts.

## Not done yet
Rate limiting, automated tests, per-role DB users (RBAC is enforced in the app layer on one read-only DB role), token-level streaming.
