"""AST firewall: a single read-only SELECT over role-allowed tables and columns."""
import sqlglot
from sqlglot import exp

_NAMES = ["Insert", "Update", "Delete", "Drop", "Create", "Alter", "Command", "Copy",
          "Merge", "TruncateTable", "Set", "Into", "Grant", "Use", "Transaction",
          "Commit", "Rollback", "Lock"]
BLOCKED_NODES = tuple(getattr(exp, n) for n in _NAMES if hasattr(exp, n))
BLOCKED_FUNCS = {"pg_sleep", "pg_read_file", "pg_read_binary_file", "pg_ls_dir", "lo_import",
                 "lo_export", "dblink", "pg_terminate_backend", "pg_cancel_backend",
                 "set_config", "current_setting", "pg_advisory_lock", "pg_stat_file"}


class Rejected(Exception):
    pass


def validate(sql: str, allowed_tables: set, max_rows: int, deny_cols: dict | None = None) -> str:
    deny_cols = deny_cols or {}
    try:
        stmts = [s for s in sqlglot.parse(sql, read="postgres") if s]
    except sqlglot.errors.ParseError as e:
        raise Rejected(f"Syntax error: {str(e)[:300]}")
    if len(stmts) != 1:
        raise Rejected("Exactly one statement is allowed.")
    tree = stmts[0]
    if not isinstance(tree, (exp.Select, exp.Union)):
        raise Rejected("Only SELECT statements are allowed.")
    for node in tree.walk():
        node = node[0] if isinstance(node, tuple) else node
        if isinstance(node, BLOCKED_NODES):
            raise Rejected(f"Forbidden operation: {type(node).__name__}.")
        if isinstance(node, exp.Func):
            name = (node.name if isinstance(node, exp.Anonymous) else node.sql_name()).lower()
            if name in BLOCKED_FUNCS:
                raise Rejected(f"Forbidden function: {name}.")
    ctes = {c.alias.lower() for c in tree.find_all(exp.CTE)}
    tables = []
    for t in tree.find_all(exp.Table):
        if t.name.lower() in ctes:
            continue
        if t.db and t.db.lower() != "public":
            raise Rejected(f"Schema '{t.db}' is not accessible.")
        if t.name.lower() not in allowed_tables:
            raise Rejected(f"Table '{t.name}' does not exist or your role cannot access it.")
        tables.append(t)
    alias = {(t.alias or t.name).lower(): t.name.lower() for t in tables}
    denied = {c for t in alias.values() for c in deny_cols.get(t, ())}
    if denied:
        for s in tree.find_all(exp.Star):
            if not isinstance(s.parent, exp.Count):
                raise Rejected("SELECT * is not allowed on tables with restricted columns; list columns explicitly.")
        for col in tree.find_all(exp.Column):
            n = col.name.lower()
            hit = n in deny_cols.get(alias.get(col.table.lower(), ""), ()) if col.table else n in denied
            if hit:
                raise Rejected(f"Column '{n}' is restricted for your role.")
    if not tree.args.get("limit"):
        tree = tree.limit(max_rows)
    return tree.sql(dialect="postgres")
