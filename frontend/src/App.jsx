import { useState, useRef, useEffect } from "react";
import ReactMarkdown from "react-markdown";
import { BarChart, Bar, LineChart, Line, ScatterChart, Scatter, PieChart, Pie, Cell, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from "recharts";

const COLORS = ["#0E7C86", "#B7791F", "#5B6B8C", "#9A3B3B", "#4F7F4A", "#7A5C99"];
const TYPES = ["bar", "line", "scatter", "pie"];
const EXAMPLES = [
  "Top 5 customers by total order value, as a bar chart",
  "Monthly revenue for completed orders over the last 4 months, as a line chart",
  "Revenue share by product category",
];
const call = (auth, path, opts = {}) =>
  fetch(path, { ...opts, headers: { "Content-Type": "application/json", Authorization: `Bearer ${auth.token}` } });
const isNum = (rows, i) => rows.length > 0 && rows.every((r) => r[i] !== null && r[i] !== "" && !isNaN(Number(r[i])));

function Login({ onAuth }) {
  const [u, setU] = useState(""), [p, setP] = useState(""), [err, setErr] = useState("");
  async function submit(e) {
    e.preventDefault();
    const res = await fetch("/api/login", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ username: u, password: p }) });
    if (!res.ok) return setErr("Wrong username or password.");
    onAuth(await res.json());
  }
  return (
    <form onSubmit={submit} className="mx-auto mt-24 max-w-sm space-y-3 px-4">
      <h1 className="text-xl font-bold">Sign in</h1>
      <input value={u} onChange={(e) => setU(e.target.value)} aria-label="Username" placeholder="Username" className="w-full border border-line bg-white px-3 py-2 text-sm" />
      <input value={p} onChange={(e) => setP(e.target.value)} type="password" aria-label="Password" placeholder="Password" className="w-full border border-line bg-white px-3 py-2 text-sm" />
      {err && <p className="text-sm text-danger">{err}</p>}
      <button className="w-full bg-accent px-4 py-2 text-sm font-medium text-white">Sign in</button>
      <p className="text-xs text-ink/60">Demo accounts: admin / admin123, analyst / analyst123, junior / junior123</p>
    </form>
  );
}

function Chart({ columns, rows, x, y, type, swap }) {
  const xi = columns.indexOf(x), yi = columns.indexOf(y), numX = isNum(rows, xi);
  const sw = swap && type !== "bar";
  const xNum = sw || numX;
  const data = rows.map((r) => {
    const a = numX ? Number(r[xi]) : String(r[xi]), b = Number(r[yi]);
    return sw ? { x: b, y: Number(r[xi]) } : { x: a, y: b };
  });
  if (xNum && type !== "bar" && type !== "pie") data.sort((p, q) => p.x - q.x);
  const [xn, yn] = sw ? [y, x] : [x, y];
  const grid = <CartesianGrid stroke="#D5DBE1" vertical={false} />;
  const xAxis = <XAxis dataKey="x" name={xn} type={xNum ? "number" : "category"} domain={["auto", "auto"]} tick={{ fontSize: 12 }} />;
  const yAxis = <YAxis dataKey={type === "scatter" ? "y" : undefined} name={yn} tick={{ fontSize: 12 }} />;
  return (
    <div className="h-64 w-full" role="img" aria-label={`${type} chart of ${y} by ${x}`}>
      <ResponsiveContainer>
        {type === "pie" ? (
          <PieChart><Pie data={data} dataKey="y" nameKey="x" outerRadius={90} label>{data.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}</Pie><Tooltip /></PieChart>
        ) : type === "line" ? (
          <LineChart data={data}>{grid}{xAxis}{yAxis}<Tooltip /><Line dataKey="y" name={yn} stroke="#0E7C86" strokeWidth={2} dot={false} /></LineChart>
        ) : type === "scatter" ? (
          <ScatterChart>{grid}{xAxis}{yAxis}<Tooltip /><Scatter data={data} fill="#0E7C86" /></ScatterChart>
        ) : swap ? (
          <BarChart data={data} layout="vertical">{grid}<XAxis type="number" tick={{ fontSize: 12 }} /><YAxis type="category" dataKey="x" width={90} tick={{ fontSize: 12 }} /><Tooltip /><Bar dataKey="y" name={y} fill="#0E7C86" /></BarChart>
        ) : (
          <BarChart data={data}>{grid}<XAxis dataKey="x" tick={{ fontSize: 12 }} /><YAxis tick={{ fontSize: 12 }} /><Tooltip /><Bar dataKey="y" name={y} fill="#0E7C86" /></BarChart>
        )}
      </ResponsiveContainer>
    </div>
  );
}

function Table({ columns, rows }) {
  return (
    <div className="max-h-72 overflow-auto border border-line bg-white">
      <table className="w-full text-sm">
        <thead className="sticky top-0 bg-paper text-left"><tr>{columns.map((c) => <th key={c} className="px-3 py-2 font-medium">{c}</th>)}</tr></thead>
        <tbody>{rows.slice(0, 100).map((r, i) => (
          <tr key={i} className="border-t border-line">{r.map((v, j) => <td key={j} className="px-3 py-1.5 font-mono text-xs">{String(v)}</td>)}</tr>
        ))}</tbody>
      </table>
    </div>
  );
}

const btn = (on) => `border px-3 py-1 text-xs ${on ? "border-accent bg-accent text-white" : "border-line bg-white"} disabled:opacity-40`;

function Turn({ t, auth }) {
  const [type, setType] = useState(null), [swap, setSwap] = useState(false), [err, setErr] = useState("");
  const res = t.result, base = res?.chart, cur = type || base?.type;
  const hasChart = base && base.type !== "table";
  const canSwap = hasChart && (cur === "bar" || (cur !== "pie" && isNum(res.rows, res.columns.indexOf(base.x))));

  async function exportAs(fmt) {
    setErr("");
    const body = { title: t.q, summary: t.summary || "", columns: res.columns, rows: res.rows, chart: hasChart ? { type: cur, x: base.x, y: base.y, swap } : { type: "table" } };
    const r = await call(auth, `/api/export/${fmt}`, { method: "POST", body: JSON.stringify(body) });
    if (!r.ok) return setErr("Export failed. Try again.");
    const a = document.createElement("a");
    a.href = URL.createObjectURL(await r.blob());
    a.download = `query-result.${fmt}`;
    a.click();
    URL.revokeObjectURL(a.href);
  }

  return (
    <section className="space-y-3">
      <p className="ml-auto max-w-xl bg-ink px-4 py-2 text-sm text-white">{t.q}</p>
      <div className="space-y-3 border border-line bg-white p-4">
        {t.busy && <p className="text-sm text-accent" aria-live="polite">{t.status}…</p>}
        {t.summary && <div className="md text-sm"><ReactMarkdown>{t.summary}</ReactMarkdown></div>}
        {hasChart && (
          <>
            <div className="flex flex-wrap gap-1" role="toolbar" aria-label="Chart options">
              {TYPES.map((k) => <button key={k} aria-pressed={cur === k} onClick={() => { setType(k); if (k === "pie") setSwap(false); }} className={btn(cur === k)}>{k}</button>)}
              <button disabled={!canSwap} aria-pressed={swap} onClick={() => setSwap(!swap)} className={btn(swap)}>Swap axes</button>
            </div>
            <Chart {...res} x={base.x} y={base.y} type={cur} swap={swap && canSwap} />
          </>
        )}
        {res && <Table columns={res.columns} rows={res.rows} />}
        {res?.truncated && <p className="text-xs text-amber">Results were cut at the row limit.</p>}
        {res && (
          <div className="flex items-center gap-1">
            <span className="mr-1 text-xs text-ink/60">Export</span>
            {["csv", "xlsx", "pdf"].map((f) => <button key={f} onClick={() => exportAs(f)} className={btn(false)}>{f.toUpperCase()}</button>)}
            {err && <span className="ml-2 text-xs text-danger">{err}</span>}
          </div>
        )}
        {t.fail && <p className="text-sm text-danger">{t.fail}</p>}
        {t.fatal && <p className="text-sm text-danger">Connection problem: {t.fatal}</p>}
        {t.attempts.length > 0 && (
          <details className="text-sm">
            <summary className="cursor-pointer text-ink/70">SQL and checks ({t.attempts.length} {t.attempts.length === 1 ? "attempt" : "attempts"}{t.cached ? ", reused a saved query" : ""})</summary>
            {t.attempts.map((a, i) => (
              <div key={i} className="mt-2">
                <pre className="overflow-auto bg-paper p-3 font-mono text-xs">{a.sql}</pre>
                {a.error && <p className="mt-1 font-mono text-xs text-danger">{a.error}</p>}
              </div>
            ))}
          </details>
        )}
      </div>
    </section>
  );
}

function Approvals({ auth }) {
  const [items, setItems] = useState([]);
  useEffect(() => {
    let on = true;
    const tick = async () => { const r = await call(auth, "/api/approvals"); if (r.ok && on) setItems(await r.json()); };
    tick();
    const h = setInterval(tick, 3000);
    return () => { on = false; clearInterval(h); };
  }, [auth]);
  async function decide(tid, approve) {
    await call(auth, "/api/approvals/decide", { method: "POST", body: JSON.stringify({ thread_id: tid, approve }) });
    setItems((i) => i.filter((x) => x.tid !== tid));
  }
  if (!items.length) return null;
  return (
    <section aria-live="polite" className="space-y-3 border border-amber bg-white p-4">
      <h2 className="text-sm font-bold">Queries waiting for your approval</h2>
      {items.map((it) => (
        <div key={it.tid} className="space-y-1 border-t border-line pt-3 text-sm">
          <p><b>{it.user}</b> asked: {it.question}</p>
          <p className="text-amber">Held because of {it.reason}.</p>
          <pre className="overflow-auto bg-paper p-2 font-mono text-xs">{it.sql}</pre>
          <div className="flex gap-2">
            <button onClick={() => decide(it.tid, true)} className={btn(true)}>Approve</button>
            <button onClick={() => decide(it.tid, false)} className={btn(false)}>Reject</button>
          </div>
        </div>
      ))}
    </section>
  );
}

export default function App() {
  const [auth, setAuth] = useState(() => { try { return JSON.parse(sessionStorage.getItem("auth")); } catch { return null; } });
  const [turns, setTurns] = useState([]), [q, setQ] = useState(""), [busy, setBusy] = useState(false);
  const convo = useRef(crypto.randomUUID()), end = useRef(null);
  useEffect(() => end.current?.scrollIntoView({ behavior: "smooth" }), [turns]);
  const signIn = (a) => { try { sessionStorage.setItem("auth", JSON.stringify(a)); } catch {} setAuth(a); };
  const signOut = () => { try { sessionStorage.removeItem("auth"); } catch {} setAuth(null); setTurns([]); convo.current = crypto.randomUUID(); };
  if (!auth) return <Login onAuth={signIn} />;

  async function consume(url, body, patch) {
    let pending = null;
    const handle = (raw) => {
      const ev = /event: (\w+)/.exec(raw)?.[1], d = JSON.parse(/data: (.*)/.exec(raw)?.[1] || "{}");
      if (ev === "status") patch((x) => ({ ...x, status: d.text }));
      if (ev === "cache") patch((x) => ({ ...x, cached: true }));
      if (ev === "sql") patch((x) => ({ ...x, attempts: [...x.attempts, { sql: d.sql }] }));
      if (ev === "retry") patch((x) => ({ ...x, attempts: x.attempts.map((a, i) => (i === x.attempts.length - 1 ? { ...a, error: d.error } : a)) }));
      if (ev === "pending") { pending = d.thread_id; patch((x) => ({ ...x, status: `Waiting for an administrator to approve (${d.reason})` })); }
      if (ev === "result") patch((x) => ({ ...x, result: d }));
      if (ev === "summary") patch((x) => ({ ...x, summary: d.text }));
      if (ev === "fail") patch((x) => ({ ...x, fail: d.error }));
    };
    const res = await call(auth, url, { method: "POST", body: JSON.stringify(body) });
    if (res.status === 401) return signOut();
    if (!res.ok || !res.body) throw new Error(`server returned ${res.status}`);
    const reader = res.body.getReader(), dec = new TextDecoder();
    let buf = "";
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      buf += dec.decode(value, { stream: true });
      let i;
      while ((i = buf.indexOf("\n\n")) >= 0) { handle(buf.slice(0, i)); buf = buf.slice(i + 2); }
    }
    if (pending) await consume(`/api/threads/${encodeURIComponent(pending)}/resume`, {}, patch);
  }

  async function ask(question) {
    if (!question.trim() || busy) return;
    setBusy(true); setQ("");
    const id = Date.now();
    const patch = (fn) => setTurns((ts) => ts.map((x) => (x.id === id ? fn(x) : x)));
    setTurns((ts) => [...ts, { id, q: question, attempts: [], busy: true, status: "Reading schema" }]);
    try { await consume("/api/ask", { question, conversation_id: convo.current }, patch); }
    catch (e) { patch((x) => ({ ...x, fatal: e.message })); }
    patch((x) => ({ ...x, busy: false }));
    setBusy(false);
  }

  return (
    <div className="mx-auto flex min-h-screen max-w-3xl flex-col px-4">
      <header className="flex items-end justify-between border-b border-line py-5">
        <div>
          <h1 className="text-xl font-bold">Ask your database</h1>
          <p className="text-sm text-ink/70">Questions become read-only SQL. Every query is checked before it runs.</p>
        </div>
        <div className="text-right text-xs text-ink/70">
          <p>{auth.name} ({auth.role.replace("_", " ")})</p>
          <button onClick={signOut} className="underline">Sign out</button>
        </div>
      </header>
      <main className="flex-1 space-y-6 py-6">
        {auth.role === "admin" && <Approvals auth={auth} />}
        {turns.length === 0 && (
          <div className="space-y-2">
            <p className="text-sm text-ink/70">Try one, then ask follow-ups like “only the top 3”:</p>
            {EXAMPLES.map((e) => <button key={e} onClick={() => ask(e)} className="block w-full border border-line bg-white px-4 py-2 text-left text-sm hover:border-accent">{e}</button>)}
          </div>
        )}
        {turns.map((t) => <Turn key={t.id} t={t} auth={auth} />)}
        <div ref={end} />
      </main>
      <form onSubmit={(e) => { e.preventDefault(); ask(q); }} className="sticky bottom-0 flex gap-2 border-t border-line bg-paper py-4">
        <input value={q} onChange={(e) => setQ(e.target.value)} maxLength={500} placeholder="Ask a question about orders, customers or products" aria-label="Question" className="flex-1 border border-line bg-white px-4 py-2 text-sm" />
        <button disabled={busy || !q.trim()} className="bg-accent px-5 py-2 text-sm font-medium text-white disabled:opacity-40">Run query</button>
      </form>
    </div>
  );
}
