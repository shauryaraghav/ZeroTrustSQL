import csv, io, re
from xml.sax.saxutils import escape


def _safe(v):  # neutralise spreadsheet formula injection
    return "'" + v if isinstance(v, str) and v[:1] in ("=", "+", "-", "@") else v


def to_csv(b):
    s = io.StringIO()
    w = csv.writer(s)
    w.writerow(b.columns)
    w.writerows([[_safe(v) for v in r] for r in b.rows])
    return s.getvalue().encode("utf-8-sig")


def to_xlsx(b):
    from openpyxl import Workbook
    from openpyxl.chart import BarChart, LineChart, PieChart, ScatterChart, Reference, Series
    from openpyxl.utils import get_column_letter
    wb = Workbook()
    ws = wb.active
    ws.title = "Results"
    ws.append(b.columns)
    for r in b.rows:
        ws.append([_safe(v) for v in r])
    c, n = b.chart or {}, len(b.rows)
    if n and c.get("type") in ("bar", "line", "scatter", "pie") and c.get("x") in b.columns and c.get("y") in b.columns:
        xi, yi, t = b.columns.index(c["x"]) + 1, b.columns.index(c["y"]) + 1, c["type"]
        ch = {"bar": BarChart, "line": LineChart, "pie": PieChart, "scatter": ScatterChart}[t]()
        ch.title = b.title[:80]
        if t == "scatter":
            s = Series(Reference(ws, min_col=yi, min_row=2, max_row=n + 1), Reference(ws, min_col=xi, min_row=2, max_row=n + 1))
            s.marker.symbol = "circle"
            s.graphicalProperties.line.noFill = True
            ch.series.append(s)
        else:
            ch.add_data(Reference(ws, min_col=yi, min_row=1, max_row=n + 1), titles_from_data=True)
            ch.set_categories(Reference(ws, min_col=xi, min_row=2, max_row=n + 1))
            if t == "bar" and c.get("swap"):
                ch.type = "bar"
        ws.add_chart(ch, f"{get_column_letter(len(b.columns) + 2)}2")
    out = io.BytesIO()
    wb.save(out)
    return out.getvalue()


def _chart_png(b):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    c = b.chart or {}
    t = c.get("type")
    if t not in ("bar", "line", "scatter", "pie") or c.get("x") not in b.columns or c.get("y") not in b.columns:
        return None
    try:
        xi, yi = b.columns.index(c["x"]), b.columns.index(c["y"])
        xs, ys = [r[xi] for r in b.rows], [float(r[yi]) for r in b.rows]
        if c.get("swap") and t in ("line", "scatter"):
            xs, ys = ys, [float(x) for x in xs]
        fig, ax = plt.subplots(figsize=(7, 3.6))
        lab = [str(x) for x in xs]
        if t == "pie":
            ax.pie(ys, labels=lab)
        elif t == "bar":
            (ax.barh if c.get("swap") else ax.bar)(lab, ys, color="#0E7C86")
        elif t == "line":
            ax.plot(lab if not c.get("swap") else xs, ys, color="#0E7C86")
        else:
            ax.scatter(xs if c.get("swap") else range(len(xs)), ys, color="#0E7C86")
        plt.xticks(rotation=30, ha="right", fontsize=7)
        fig.tight_layout()
        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=150)
        plt.close(fig)
        buf.seek(0)
        return buf
    except Exception:
        return None


def to_pdf(b):
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    st, buf = getSampleStyleSheet(), io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=landscape(A4))
    out = [Paragraph(escape(b.title), st["Title"])]
    if b.summary:
        out += [Paragraph(escape(re.sub(r"[*_`#>]", "", b.summary)).replace("\n", "<br/>"), st["BodyText"]), Spacer(1, 12)]
    png = _chart_png(b)
    if png:
        out += [Image(png, width=480, height=247), Spacer(1, 12)]
    t = Table([b.columns] + [[str(v)[:40] for v in r] for r in b.rows[:60]], repeatRows=1)
    t.setStyle(TableStyle([("FONTSIZE", (0, 0), (-1, -1), 8), ("GRID", (0, 0), (-1, -1), .25, colors.grey),
                           ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E8ECEF"))]))
    out.append(t)
    if len(b.rows) > 60:
        out.append(Paragraph(f"Showing 60 of {len(b.rows)} rows.", st["Italic"]))
    doc.build(out)
    return buf.getvalue()
