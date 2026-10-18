"""PDF export for the statement and the insight report (reportlab for layout, matplotlib for charts)."""
from __future__ import annotations

import io
from datetime import date

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from reportlab.lib import colors  # noqa: E402
from reportlab.lib.pagesizes import A4  # noqa: E402
from reportlab.lib.utils import ImageReader  # noqa: E402
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet  # noqa: E402
from reportlab.lib.units import mm  # noqa: E402
from reportlab.platypus import Image, KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle  # noqa: E402
from xml.sax.saxutils import escape  # noqa: E402

import tracker_core as core  # noqa: E402

INK, MUTED, GOLD = colors.HexColor("#16302f"), colors.HexColor("#52706b"), colors.HexColor("#a98425")
GREEN, RED = "#1d9a72", "#d4604f"
PALETTE = ["#a98425", "#1d9a72", "#d4604f", "#3f86bd", "#8b6fd0", "#d08a3f", "#3fa7b0", "#c46a9c"]
styles = getSampleStyleSheet()
H = ParagraphStyle("h", parent=styles["Heading2"], fontName="Times-Bold", textColor=INK, fontSize=13, spaceBefore=10, spaceAfter=4)
SMALL = ParagraphStyle("s", parent=styles["Normal"], fontName="Helvetica", fontSize=8.5, textColor=MUTED)


def _title_block(title: str, sub: str, profile: dict | None):
    t = Table([[Paragraph(f'<font color="white" size="18"><b>{escape(title)}</b></font><br/><font color="#d8b76a" size="9">{escape(sub)}</font>', styles["Normal"]),
                Paragraph(f'<para align="right"><font color="white" size="9">{escape((profile or {}).get("name", ""))}<br/>'
                          f'<font color="#8aa7a2">Created {date.today():%d %b %Y}</font></font></para>', styles["Normal"])]],
              colWidths=[110 * mm, 70 * mm])
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#0a1d22")), ("LEFTPADDING", (0, 0), (-1, -1), 10),
                           ("RIGHTPADDING", (0, 0), (-1, -1), 10), ("TOPPADDING", (0, 0), (-1, -1), 12), ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
                           ("LINEBELOW", (0, 0), (-1, -1), 3, colors.HexColor("#d8b76a")), ("VALIGN", (0, 0), (-1, -1), "TOP")]))
    return t


def _figures(items):
    cells = [[Paragraph(f'<font size="8" color="#52706b">{escape(k)}</font><br/><font name="Times-Bold" size="13">{escape(v)}</font>', styles["Normal"]) for k, v in items]]
    t = Table(cells, colWidths=[180 * mm / len(items)] * len(items))
    t.setStyle(TableStyle([("LINEABOVE", (0, 0), (-1, 0), 0.5, colors.HexColor("#c8d4d0")), ("LINEBELOW", (0, 0), (-1, 0), 0.5, colors.HexColor("#c8d4d0")),
                           ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]))
    return t


def _footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(MUTED)
    canvas.drawCentredString(A4[0] / 2, 12 * mm, f"Page {doc.page}, amounts in {core.BASE}")
    canvas.restoreState()


def _safe(s: str) -> str:
    return escape(s.encode("latin-1", "replace").decode("latin-1"))


def statement_pdf(st: dict, profile: dict | None, settings: dict, kind: str = "all") -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=15 * mm, rightMargin=15 * mm, topMargin=12 * mm, bottomMargin=20 * mm,
                            title="Account statement", author=(profile or {}).get("name", ""))
    name = {"income": "Income statement", "expense": "Expense statement"}.get(kind, "Account statement")
    flow = [_title_block(name, f"{st['from']} to {st['to']}", profile), Spacer(1, 8),
            _figures([("Balance brought forward", core.fmt(st["brought"])), ("Total credit", "+" + core.fmt(st["credits"])),
                      ("Total debit", "-" + core.fmt(st["debits"])), ("Closing balance", core.fmt(st["closing"]))]), Spacer(1, 8)]
    body = [["Date and time", "Details", "Method", "Debit", "Credit", "Balance"]]
    month_rows: list[int] = []
    if st["opening_row"]:
        body.append([st["opening_row"], "Opening balance", "", "", "", core.fmt(settings["opening_minor"])])
    elif kind == "all":
        body.append([st["from"], "Balance brought forward", "", "", "", core.fmt(st["brought"])])
    sums: dict[str, list[int]] = {}
    for r in st["rows"]:
        o = sums.setdefault(r["txn"]["date"][:7], [0, 0])
        o[0] += r["credit"]
        o[1] += 0 if r["memo"] else r["debit"]
    last = ""
    for r in st["rows"]:
        t = r["txn"]
        if t["date"][:7] != last:
            last = t["date"][:7]
            c, d = sums[last]
            month_rows.append(len(body))
            body.append([f"{date.fromisoformat(last + '-01'):%B %Y}      Credit +{core.fmt(c)}      Debit -{core.fmt(d)}", "", "", "", "", ""])
        detail = Paragraph(_safe(core.describe(t) + (("  " + " ".join("#" + g for g in t["tags"])) if t["tags"] else "") + ("  (card, not deducted)" if r["memo"] else "")),
                           ParagraphStyle("c", fontName="Helvetica", fontSize=8.5, leading=10))
        body.append([core.when(t), detail, t["mode"] if t["type"] == "expense" else "", core.fmt(r["debit"]) if r["debit"] else "",
                     core.fmt(r["credit"]) if r["credit"] else "", core.fmt(r["balance"])])
    table = Table(body, colWidths=[24 * mm, 64 * mm, 24 * mm, 22 * mm, 22 * mm, 24 * mm], repeatRows=1)
    table.setStyle(TableStyle([("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 8.5), ("FONT", (0, 1), (-1, -1), "Helvetica", 8.5),
                               ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#ebf1ee")), ("TEXTCOLOR", (0, 0), (-1, -1), INK),
                               ("TEXTCOLOR", (3, 1), (3, -1), colors.HexColor("#be4637")), ("TEXTCOLOR", (4, 1), (4, -1), colors.HexColor("#188262")),
                               ("ALIGN", (3, 0), (-1, -1), "RIGHT"), ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8faf9")]),
                               ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]))
    for i in month_rows:
        table.setStyle(TableStyle([("SPAN", (0, i), (-1, i)), ("BACKGROUND", (0, i), (-1, i), colors.HexColor("#d8b76a")), ("FONT", (0, i), (-1, i), "Helvetica-Bold", 9),
                                   ("TEXTCOLOR", (0, i), (-1, i), colors.HexColor("#1b1405")), ("ALIGN", (0, i), (-1, i), "LEFT")]))
    flow.append(table)
    doc.build(flow, onFirstPage=_footer, onLaterPages=_footer)
    return buf.getvalue()


def _fig_png(fig) -> io.BytesIO:
    b = io.BytesIO()
    fig.savefig(b, format="png", dpi=170, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    b.seek(0)
    return b


def _style_ax(ax):
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.tick_params(colors="#52706b", labelsize=7)
    ax.grid(axis="y", color="#16302f", alpha=0.12)
    ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v / 1000:g}k" if abs(v) >= 1000 else f"{v:g}"))


def chart_images(ds: dict) -> list[tuple[str, io.BytesIO]]:
    out = []
    w, h = 7.0, 2.1
    if ds["totals"]["expense"] > 0:
        fig, ax = plt.subplots(figsize=(w, h))
        xs = [d["date"][5:] for d in ds["daily"]]
        ys = [d["expense"] / 100 for d in ds["daily"]]
        ax.fill_between(range(len(ys)), ys, color=RED, alpha=0.2)
        ax.plot(ys, color=RED, lw=1.6)
        step = max(1, len(xs) // 7)
        ax.set_xticks(range(0, len(xs), step), [xs[i] for i in range(0, len(xs), step)])
        _style_ax(ax)
        out.append(("Daily spending", _fig_png(fig)))
    fig, ax = plt.subplots(figsize=(w, h))
    ys = [b["balance"] / 100 for b in ds["balance"]]
    ax.step(range(len(ys)), ys, where="post", color="#a98425", lw=2)
    step = max(1, len(ys) // 7)
    ax.set_xticks(range(0, len(ys), step), [ds["balance"][i]["date"][5:] for i in range(0, len(ys), step)])
    _style_ax(ax)
    out.append(("Balance over time", _fig_png(fig)))
    if len(ds["monthly"]) > 1:
        fig, ax = plt.subplots(figsize=(w, h))
        xs = list(range(len(ds["monthly"])))
        ax.bar([x - 0.2 for x in xs], [m["income"] / 100 for m in ds["monthly"]], 0.4, color=GREEN, label="Income")
        ax.bar([x + 0.2 for x in xs], [m["expense"] / 100 for m in ds["monthly"]], 0.4, color=RED, label="Spent")
        ax.set_xticks(xs, [m["month"] for m in ds["monthly"]])
        ax.legend(fontsize=7, frameon=False)
        _style_ax(ax)
        out.append(("Income and spending by month", _fig_png(fig)))
    if ds["totals"]["expense"] > 0:
        fig, ax = plt.subplots(figsize=(4.6, 2.6))
        cats = ds["categories"][:7]
        rest = sum(v for _, v in ds["categories"][7:])
        labels = [c for c, _ in cats] + (["Everything else"] if rest else [])
        vals = [v / 100 for _, v in cats] + ([rest / 100] if rest else [])
        ax.pie(vals, labels=None, colors=PALETTE[: len(vals)], startangle=90, counterclock=False, wedgeprops={"width": 0.42, "edgecolor": "white"})
        tot = sum(vals)
        ax.legend([f"{l}  {v / tot:.0%}" for l, v in zip(labels, vals)], loc="center left", bbox_to_anchor=(1, 0.5), fontsize=8, frameon=False)
        out.append(("Where the money went", _fig_png(fig)))
        fig, ax = plt.subplots(figsize=(w, h))
        ax.bar([b["label"] for b in ds["histogram"]], [b["count"] for b in ds["histogram"]], color="#a98425", width=0.95)
        ax.yaxis.set_major_locator(matplotlib.ticker.MaxNLocator(integer=True))
        _style_ax(ax)
        out.append(("Size of expenses (number per amount range)", _fig_png(fig)))
        fig, ax = plt.subplots(figsize=(w, 1.5))
        ax.barh([m for m, _ in ds["modes"]][::-1], [v / 100 for _, v in ds["modes"]][::-1], color="#a98425")
        ax.tick_params(colors="#16302f", labelsize=8)
        for s in ("top", "right"):
            ax.spines[s].set_visible(False)
        out.append(("Payment methods", _fig_png(fig)))
    return out


def insight_pdf(ds: dict, profile: dict | None) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=15 * mm, rightMargin=15 * mm, topMargin=12 * mm, bottomMargin=20 * mm, title="Spending insight")
    t = ds["totals"]
    flow = [_title_block("Spending insight", f"{ds['from']} to {ds['to']}", profile), Spacer(1, 8),
            _figures([("Income", core.fmt(t["income"])), ("Spent", core.fmt(t["expense"])), ("Net", core.fmt(t["net"])),
                      ("Average per day", core.fmt(ds["avg_per_day"]))])]
    for title, img in chart_images(ds):
        iw, ih = ImageReader(img).getSize()
        img.seek(0)
        width = (120 if "money went" in title else 170) * mm
        flow.append(KeepTogether([Paragraph(escape(title), H), Image(img, width=width, height=width * ih / iw)]))
    doc.build(flow, onFirstPage=_footer, onLaterPages=_footer)
    return buf.getvalue()