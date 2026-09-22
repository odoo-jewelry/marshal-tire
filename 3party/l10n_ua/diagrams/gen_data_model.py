#!/usr/bin/env python3
"""Generate diagrams/data_model.svg — the HR data-model (ER) diagram.

Hand-authored, dependency-free SVG in the same visual language as
gen_full_architecture.py. Re-run after model changes:

    python3 diagrams/gen_data_model.py
"""
import os
from xml.sax.saxutils import escape

FONT = "'Segoe UI', 'Helvetica Neue', Roboto, Arial, sans-serif"
LINEFONT = "'DejaVu Sans', 'Segoe UI', Arial, sans-serif"  # carries → reliably
MONO = "'DejaVu Sans Mono', 'SFMono-Regular', Consolas, monospace"

PAL = {
    "emerald":("#37955f", "#e8f6ed", "#bfe4cd"),
    "sky":    ("#2f86bd", "#e7f2fa", "#c3ddef"),
    "purple": ("#7d5fb0", "#f1ebf9", "#dcccf0"),
    "rose":   ("#b23a5c", "#f9e8ee", "#eec4d1"),
    "slate":  ("#475569", "#eef1f5", "#cbd5e1"),
}

# entity: (key, model name, accent, [ (field, type, flag) ])  flag: pk|req|fk|''
ENT = {
    "employee": ("hr.employee", "emerald", [
        ("id", "integer", "pk"),
        ("name", "char", "req"),
        ("rnokpp", "char", ""),
        ("passport_id", "char", ""),
        ("department_id", "→ hr.department", "fk"),
        ("job_id", "→ hr.job", "fk"),
    ]),
    "contract": ("hr.contract", "sky", [
        ("id", "integer", "pk"),
        ("employee_id", "→ hr.employee", "fk"),
        ("date_start", "date", "req"),
        ("wage", "monetary", "req"),
    ]),
    "order": ("hr.order", "purple", [
        ("id", "integer", "pk"),
        ("name", "char", "req"),
        ("order_type", "selection", "req"),
        ("content", "html", ""),
        ("employee_id", "→ hr.employee", "fk"),
    ]),
    "certificate": ("hr.certificate", "rose", [
        ("id", "integer", "pk"),
        ("certificate_type_id", "FK", "fk"),
        ("employee_id", "→ hr.employee", "fk"),
        ("state", "selection", ""),
        ("body", "html", ""),
    ]),
    "template": ("hr.order.template", "slate", [
        ("id", "integer", "pk"),
        ("name", "char", "req"),
        ("order_type", "selection", "req"),
        ("body", "html", ""),
    ]),
    "cert_type": ("hr.certificate.type", "slate", [
        ("id", "integer", "pk"),
        ("name", "char", "req"),
        ("code", "char", "req"),
        ("template_body", "html", ""),
    ]),
}

# relationships: (parent, child, one_label, many_label)
REL = [
    ("employee", "contract", "1", "N"),
    ("employee", "order", "1", "N"),
    ("employee", "certificate", "1", "N"),
    ("order", "template", "N", "1"),
    ("certificate", "cert_type", "N", "1"),
]

W, MARGIN = 1080, 34
HEAD_H, ROW_H = 30, 19
CARD_W = 236
COL_X = {1: MARGIN, 2: MARGIN + 372, 3: MARGIN + 744}


def esc(s):
    return escape(str(s))


def txt(x, y, s, size, color, weight="normal", family=FONT, anchor="start",
        style=""):
    st = f" font-style='{style}'" if style else ""
    return (f"<text x='{x}' y='{y}' font-family=\"{family}\" font-size='{size}' "
            f"fill='{color}' font-weight='{weight}' text-anchor='{anchor}'{st}>"
            f"{esc(s)}</text>")


def top_round(x, y, w, h, r, fill):
    d = (f"M{x},{y+h} L{x},{y+r} Q{x},{y} {x+r},{y} "
         f"L{x+w-r},{y} Q{x+w},{y} {x+w},{y+r} L{x+w},{y+h} Z")
    return f"<path d='{d}' fill='{fill}'/>"


def card_h(fields):
    return HEAD_H + 10 + len(fields) * ROW_H + 8


def render_card(x, y, key):
    name, accent, fields = ENT[key]
    head, fill, border = PAL[accent]
    h = card_h(fields)
    p = [f"<rect x='{x}' y='{y}' width='{CARD_W}' height='{h}' rx='10' "
         f"fill='{fill}' stroke='{border}' stroke-width='1.3'/>"]
    p.append(top_round(x, y, CARD_W, HEAD_H, 10, head))
    p.append(txt(x + 13, y + 20, name, 13, "#ffffff", "700", family=MONO))
    ry = y + HEAD_H + 22
    for fname, ftype, flag in fields:
        # marker
        if flag == "pk":
            p.append(f"<circle cx='{x+16}' cy='{ry-4}' r='3.2' fill='{head}'/>")
        elif flag == "req":
            p.append(txt(x + 13, ry, "*", 12, "#c0504d", "700", family=MONO))
        label = f"{fname}" + ("  " if flag == "pk" else "")
        weight = "700" if flag == "pk" else "500"
        p.append(txt(x + 26, ry, label, 11.5, "#2b3440", weight, family=MONO))
        # type / target, right aligned
        tcolor = "#7d5fb0" if flag == "fk" else "#6b7280"
        p.append(txt(x + CARD_W - 12, ry, ftype, 10.5, tcolor,
                     "600" if flag == "fk" else "400", family=LINEFONT,
                     anchor="end"))
        ry += ROW_H
    return "".join(p), h


def build():
    # ---- layout ----
    pos = {}          # key -> (x, y, h)
    # column 2 stacked
    y = 132
    for key in ("contract", "order", "certificate"):
        h = card_h(ENT[key][2])
        pos[key] = (COL_X[2], y, h)
        y += h + 34
    col2_top = pos["contract"][1]
    col2_bot = pos["certificate"][1] + pos["certificate"][2]
    # column 1: employee centred against col2 span
    eh = card_h(ENT["employee"][2])
    pos["employee"] = (COL_X[1], (col2_top + col2_bot) / 2 - eh / 2, eh)
    # column 3: template aligned to order, cert_type to certificate
    for pkey, ckey in (("order", "template"), ("certificate", "cert_type")):
        px, py, ph = pos[pkey]
        ch = card_h(ENT[ckey][2])
        pos[ckey] = (COL_X[3], py + ph / 2 - ch / 2, ch)

    H = int(col2_bot + 70)

    s = [f"<svg xmlns='http://www.w3.org/2000/svg' width='{W}' height='{H}' "
         f"viewBox='0 0 {W} {H}' font-family=\"{FONT}\">"]
    s.append(f"<rect width='{W}' height='{H}' rx='16' fill='#ffffff'/>")
    s.append(f"<rect x='2' y='2' width='{W-4}' height='{H-4}' rx='15' fill='none' "
             f"stroke='#e3e8ef' stroke-width='1.5'/>")
    s.append(txt(W / 2, 44, "Модель даних — Кадри та документи (HR)", 21,
                 "#1f2933", "700", anchor="middle"))
    s.append(txt(W / 2, 66,
                 "● первинний ключ · * обов'язкове · фіолетовим — зовнішній ключ (FK)",
                 12, "#6b7280", "400", anchor="middle", family=LINEFONT))

    # ---- relationships (draw under cards) ----
    def center_y(key):
        x, yy, h = pos[key]
        return yy + h / 2

    for parent, child, lp, lc in REL:
        px, py, ph = pos[parent]
        cx, cy, ch = pos[child]
        p_right = px + CARD_W
        c_left = cx
        y1, y2 = center_y(parent), center_y(child)
        midx = (p_right + c_left) / 2
        d = f"M{p_right},{y1} L{midx},{y1} L{midx},{y2} L{c_left},{y2}"
        s.append(f"<path d='{d}' fill='none' stroke='#9aa5b1' stroke-width='1.5'/>")
        # endpoint dots
        s.append(f"<circle cx='{p_right}' cy='{y1}' r='2.6' fill='#9aa5b1'/>")
        s.append(f"<circle cx='{c_left}' cy='{y2}' r='2.6' fill='#9aa5b1'/>")
        # cardinality labels
        s.append(txt(p_right + 8, y1 - 6, lp, 11, "#5b6672", "700",
                     family=LINEFONT))
        s.append(txt(c_left - 8, y2 - 6, lc, 11, "#5b6672", "700",
                     family=LINEFONT, anchor="end"))

    # ---- cards (on top) ----
    for key in ENT:
        x, yy, h = pos[key]
        body, _ = render_card(x, yy, key)
        s.append(body)

    s.append(txt(MARGIN, H - 16,
                 "Зв'язки: працівник 1—N договорів / наказів / довідок · "
                 "наказ N—1 шаблон · довідка N—1 тип довідки",
                 11, "#8a94a2", "400", family=LINEFONT, style="italic"))
    s.append("</svg>")
    return "".join(s)


if __name__ == "__main__":
    here = os.path.dirname(os.path.abspath(__file__))
    out = os.path.join(here, "data_model.svg")
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(build())
    print(f"wrote {out}")
