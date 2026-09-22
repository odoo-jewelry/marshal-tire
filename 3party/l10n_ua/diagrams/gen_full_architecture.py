#!/usr/bin/env python3
"""Generate diagrams/full_architecture.svg — the module-architecture map.

Hand-authored, dependency-free SVG (crisp at any zoom, renders on GitHub in
light and dark). Re-run after adding modules:

    python3 diagrams/gen_full_architecture.py
"""
import os
from xml.sax.saxutils import escape

W, MARGIN = 1240, 36
INNER = W - 2 * MARGIN
COLS, COL_GAP, ROW_GAP = 4, 20, 18
CARD_W = (INNER - (COLS - 1) * COL_GAP) // COLS
CARD_H = 150
GRID_TOP = 172

FONT = "'Segoe UI', 'Helvetica Neue', Roboto, Arial, sans-serif"
# Chain lines carry the → glyph. Some renderers (e.g. the cairosvg preview)
# resolve the UI stack to a font without → and do not per-glyph fall back, so
# DejaVu Sans — which has → — is listed first here; browsers still fall back
# to → from any family, so the arrow is safe everywhere.
CHAIN_FONT = "'DejaVu Sans', 'Segoe UI', Arial, sans-serif"
MONO = "'SFMono-Regular', 'JetBrains Mono', Consolas, 'Liberation Mono', monospace"

# domain -> (header colour, light fill, border)
PAL = {
    "slate":  ("#334155", "#e8edf3", "#cbd5e1"),
    "green":  ("#2f8f63", "#e9f6ef", "#bfe3d0"),
    "amber":  ("#bf871c", "#fbf1de", "#eddbb0"),
    "coral":  ("#cf5b57", "#fbe9e8", "#f1c9c7"),
    "purple": ("#7d5fb0", "#f1ebf9", "#dcccf0"),
    "sky":    ("#2f86bd", "#e7f2fa", "#c3ddef"),
    "wheat":  ("#b3852f", "#f7efdd", "#e6d4ad"),
    "teal":   ("#2a908d", "#e4f3f2", "#bce0de"),
    "bluegr": ("#4d6fa6", "#eaf0f9", "#c8d6ec"),
    "emerald":("#37955f", "#e8f6ed", "#bfe4cd"),
    "dorange":("#b9622a", "#f8ece1", "#ecceb4"),
    "gold":   ("#93800f", "#f4f0d4", "#e0d79e"),
    "rose":   ("#b23a5c", "#f9e8ee", "#eec4d1"),
}

CARDS = [
    ("Бухгалтерія", "green", 4,
     ["accounting · assets", "account_subconto_hr · doc_reports"],
     "План рахунків П(С)БО, ОСВ/баланс, ОЗ"),
    ("Податки", "amber", 6,
     ["tax · account_vat · fop", "tax_4df · tax_cabinet · F0103309"],
     "ПДФО/ВЗ/ЄСВ/ПДВ, ЄП, 4ДФ, кабінет ДПС"),
    ("Банки", "coral", 5,
     ["bank_sync → privat · mono", "currency_sync · payment_link"],
     "Виписки, курси НБУ, еквайринг"),
    ("ПРРО", "purple", 2,
     ["prro_base → prro_checkbox"],
     "Чеки, зміни, X/Z-звіти (Checkbox)"),
    ("Доставка", "sky", 4,
     ["delivery_base → novaposhta", "ukrposhta · meest"],
     "ТТН, відстеження, післяплата"),
    ("Маркетплейси", "wheat", 5,
     ["marketplace_base → rozetka · prom", "hotline · priceua"],
     "YML-фіди, імпорт замовлень"),
    ("Прайси постачальників", "teal", 6,
     ["prices_base → csv · xlsx · xml", "api · sftp"],
     "Імпорт прайсів, зіставлення товарів"),
    ("Договори", "bluegr", 1,
     ["agreement  (на базі OCA)"],
     "Договори, підпис, дод. угоди"),
    ("HR · Зарплата", "emerald", 13,
     ["hr_base → contract → salary", "reports · holidays · attendance · …"],
     "Кадри, КП-2010, військоблік, розрахунок ЗП"),
    ("Бюджет", "dorange", 8,
     ["budget_base → estimate · treasury", "reports · kpkvk · chart · dbf"],
     "Кошториси, КЕКВ/КПКВК, казначейство"),
    ("Освіта", "gold", 6,
     ["education_base → edebo · scholarship", "meals · edebo_xml"],
     "Контингент, ЄДЕБО, стипендії, харчування"),
    ("Медицина", "rose", 6,
     ["medecin_base → patient · clinical", "ehealth · nszu"],
     "Пацієнти, декларації ПМД, НСЗУ, eHealth"),
]

ROWS = (len(CARDS) + COLS - 1) // COLS
H = GRID_TOP + ROWS * CARD_H + (ROWS - 1) * ROW_GAP + 60


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


def card(x, y, title, key, n, lines, caption):
    head, fill, border = PAL[key]
    HEAD_H = 30
    p = [f"<g>"]
    # body
    p.append(f"<rect x='{x}' y='{y}' width='{CARD_W}' height='{CARD_H}' rx='11' "
             f"ry='11' fill='{fill}' stroke='{border}' stroke-width='1.3'/>")
    # header (top-rounded)
    p.append(top_round(x, y, CARD_W, HEAD_H, 11, head))
    p.append(txt(x + 14, y + 20, title, 13.5, "#ffffff", "600"))
    # count pill
    pill_w = 46
    px = x + CARD_W - pill_w - 10
    p.append(f"<rect x='{px}' y='{y+7}' width='{pill_w}' height='16' rx='8' "
             f"fill='#ffffff' fill-opacity='0.22'/>")
    p.append(txt(px + pill_w / 2, y + 19, f"{n} мод.", 10, "#ffffff", "600",
                 anchor="middle"))
    # module chain lines (sans — reliably carries the → glyph on all viewers)
    ly = y + HEAD_H + 24
    for ln in lines:
        p.append(txt(x + 14, ly, ln, 12, "#33404d", "600", family=CHAIN_FONT))
        ly += 19
    # caption
    p.append(txt(x + 14, y + CARD_H - 14, caption, 11, "#5b6672", "400",
                 style="italic"))
    p.append("</g>")
    return "".join(p)


def build():
    s = [f"<svg xmlns='http://www.w3.org/2000/svg' width='{W}' height='{H}' "
         f"viewBox='0 0 {W} {H}' font-family=\"{FONT}\">"]
    # canvas
    s.append(f"<rect x='0' y='0' width='{W}' height='{H}' rx='16' fill='#ffffff'/>")
    s.append(f"<rect x='2' y='2' width='{W-4}' height='{H-4}' rx='15' "
             f"fill='none' stroke='#e3e8ef' stroke-width='1.5'/>")
    # title
    s.append(txt(W / 2, 44, "Архітектура модулів — Українська локалізація Odoo 19",
                 22, "#1f2933", "700", anchor="middle"))
    s.append(txt(W / 2, 68, "68 модулів · 12 доменів над спільним базовим рівнем",
                 13, "#6b7280", "400", anchor="middle"))
    # foundation band
    by, bh = 86, 60
    bx, bw = MARGIN, INNER
    sh, sf, sb = PAL["slate"]
    s.append(f"<rect x='{bx}' y='{by}' width='{bw}' height='{bh}' rx='12' "
             f"fill='{sf}' stroke='{sb}' stroke-width='1.4'/>")
    s.append(f"<rect x='{bx}' y='{by}' width='7' height='{bh}' rx='3' fill='{sh}'/>")
    s.append(txt(bx + 24, by + 25, "БАЗОВИЙ РІВЕНЬ", 12, sh, "700"))
    s.append(txt(bx + 24, by + 45, "l10n_ua_account_base", 14, "#1f2933", "600",
                 family=MONO))
    s.append(txt(bx + bw - 20, by + 25,
                 "КВЕД · КАТОТТГ · валідація ЄДРПОУ/ІПН",
                 12, "#4b5563", "400", anchor="end"))
    s.append(txt(bx + bw - 20, by + 45,
                 "формати документів · спільні довідники",
                 12, "#4b5563", "400", anchor="end"))
    # downward connector
    cx = W / 2
    s.append(f"<line x1='{cx}' y1='{by+bh}' x2='{cx}' y2='{GRID_TOP-8}' "
             f"stroke='#9aa5b1' stroke-width='1.6'/>")
    s.append(f"<path d='M{cx-6},{GRID_TOP-14} L{cx},{GRID_TOP-6} L{cx+6},"
             f"{GRID_TOP-14}' fill='none' stroke='#9aa5b1' stroke-width='1.6' "
             f"stroke-linejoin='round' stroke-linecap='round'/>")
    s.append(txt(cx + 14, GRID_TOP - 16, "усі домени залежать від базового рівня",
                 11, "#9aa5b1", "400", style="italic"))
    # cards
    for i, (title, key, n, lines, cap) in enumerate(CARDS):
        c, r = i % COLS, i // COLS
        x = MARGIN + c * (CARD_W + COL_GAP)
        y = GRID_TOP + r * (CARD_H + ROW_GAP)
        s.append(card(x, y, title, key, n, lines, cap))
    # legend
    ly = GRID_TOP + ROWS * CARD_H + (ROWS - 1) * ROW_GAP + 26
    s.append(txt(MARGIN + 2, ly,
                 "Префікс l10n_ua_ опущено · «→» позначає залежність між модулями "
                 "· «N мод.» — кількість модулів домену",
                 11, "#8a94a2", "400", family=CHAIN_FONT, style="italic"))
    s.append("</svg>")
    return "".join(s)


if __name__ == "__main__":
    here = os.path.dirname(os.path.abspath(__file__))
    out = os.path.join(here, "full_architecture.svg")
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(build())
    print(f"wrote {out}  ({W}x{H})")
