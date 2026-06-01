"""PDF generation using fpdf2 – A3 landscape, one page, modern schedule design.

Each cell is coloured with a light version of the department colour (like
Google Calendar), with bold task name and smaller shift time below it.
"""
import logging

logger = logging.getLogger(__name__)

# ── Absence palette ───────────────────────────────────────────────────────────
_ABS = {
    'dovolena': {'bg': (254, 243, 199), 'fg': (146,  64,  14), 'label': 'Dovolena'},
    'nemoc':    {'bg': (254, 226, 226), 'fg': (153,  27,  27), 'label': 'Nemoc'},
    'lekar':    {'bg': (219, 234, 254), 'fg': ( 30,  64, 175), 'label': 'Lekar'},
    'osobni':   {'bg': (209, 250, 229), 'fg': (  6,  95,  70), 'label': 'Osobni'},
    'nahradni': {'bg': (237, 233, 254), 'fg': ( 91,  33, 182), 'label': 'Nahradni'},
    'jine':     {'bg': (229, 231, 235), 'fg': ( 55,  65,  81), 'label': 'Jine'},
    'svatek':   {'bg': (254, 249, 195), 'fg': (113,  63,  18), 'label': 'Svatek'},
}

# Palette used when a department has no colour set (D9D9D9 default)
_PALETTE = [
    (37,  99, 235),   # blue
    (  5, 150, 105),  # emerald
    (168,  85, 247),  # violet
    (234,  88,  12),  # orange
    (220,  38,  38),  # red
    (  2, 132, 199),  # sky
    (101, 163,  13),  # lime
    (217,  70, 239),  # fuchsia
    ( 15, 118, 110),  # teal
    (180,  83,   9),  # amber
]

# Czech → ASCII (Helvetica = Latin-1)
_TRANS = str.maketrans({
    'á': 'a', 'č': 'c', 'ď': 'd', 'é': 'e', 'ě': 'e', 'í': 'i',
    'ľ': 'l', 'ň': 'n', 'ó': 'o', 'ř': 'r', 'š': 's', 'ť': 't',
    'ú': 'u', 'ů': 'u', 'ý': 'y', 'ž': 'z',
    'Á': 'A', 'Č': 'C', 'Ď': 'D', 'É': 'E', 'Ě': 'E', 'Í': 'I',
    'Ľ': 'L', 'Ň': 'N', 'Ó': 'O', 'Ř': 'R', 'Š': 'S', 'Ť': 'T',
    'Ú': 'U', 'Ů': 'U', 'Ý': 'Y', 'Ž': 'Z',
    '–': '-', '—': '-',               # en/em dash
    '‘': "'", '’': "'",               # curly single quotes
    '“': '"', '”': '"',               # curly double quotes
    '…': '...', '·': '.', '×': 'x',
})


def _t(s):
    return str(s).translate(_TRANS) if s else ''


def _hex_rgb(h):
    h = (h or 'D9D9D9').lstrip('#').zfill(6)
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _dept_rgb(dept_name, dept_color_hex):
    """Vivid (saturated) dept colour – from DB or auto from palette."""
    if dept_color_hex:
        hx = dept_color_hex.lstrip('#').upper()
        if hx not in ('D9D9D9', 'FFFFFF', ''):
            return _hex_rgb(dept_color_hex)
    idx = sum(ord(c) for c in (dept_name or '')) % len(_PALETTE)
    return _PALETTE[idx]


def _pastel(r, g, b, mix=0.20):
    """Mix vivid colour with white at `mix` ratio → pastel cell background."""
    return (
        int(255 - (255 - r) * mix),
        int(255 - (255 - g) * mix),
        int(255 - (255 - b) * mix),
    )


def _darken(r, g, b, factor=0.75):
    """Darken a colour for text on pastel background."""
    return int(r * factor), int(g * factor), int(b * factor)


def generate_week_pdf(plan, grid, brigada_grid, dates, day_names):
    """Return PDF bytes – A3 landscape, Google-Calendar-style coloured cells."""
    try:
        from fpdf import FPDF
    except ImportError:
        raise RuntimeError("fpdf2 neni nainstalovano.")

    # ── Geometry ───────────────────────────────────────────────────────────
    PAGE_W, PAGE_H = 420, 297
    MX, MY = 3, 3                  # tighter margins → more row space
    IW = PAGE_W - 2 * MX          # 414 mm
    IH = PAGE_H - 2 * MY          # 291 mm

    TITLE_H = 7
    DHDR_H  = 7
    NAME_W  = IW * 0.13           # ~54 mm
    DAY_W   = (IW - NAME_W) / 7  # ~51 mm

    n_reg  = len(grid)
    n_brig = len(brigada_grid)
    SEP_H  = 3 if brigada_grid else 0
    avail  = IH - TITLE_H - DHDR_H - SEP_H
    n_rows = n_reg + n_brig
    ROW_H  = max(5.5, avail / n_rows) if n_rows else 8

    TWO_LINE = ROW_H >= 8.0       # show task + shift on separate lines

    FS_TITLE = 11
    FS_HDR   = 8
    FS_NAME  = max(8.5, min(13.0, ROW_H * 1.55))
    FS_TASK  = max(8.0, min(12.5, ROW_H * (1.4 if TWO_LINE else 1.5)))
    FS_SHIFT = max(6.5, min(10.5, ROW_H * 1.1))

    PAD = 1.5  # inner cell padding mm

    # ── PDF ────────────────────────────────────────────────────────────────
    pdf = FPDF(orientation='L', unit='mm', format='A3')
    pdf.set_auto_page_break(False)
    pdf.add_page()
    pdf.set_margins(MX, MY, MX)
    pdf.set_y(MY)

    # ── Title ──────────────────────────────────────────────────────────────
    pdf.set_fill_color(15, 40, 110)
    pdf.rect(MX, MY, IW, TITLE_H, 'F')
    pdf.set_text_color(255, 255, 255)
    pdf.set_font('Helvetica', 'B', FS_TITLE)
    title = _t(
        f"Plan smen - tyden {plan['week_number']}/{plan['year']}   "
        f"{dates[0].strftime('%d.%m.')} - {dates[6].strftime('%d.%m.%Y')}"
    )
    pdf.set_xy(MX + PAD, MY)
    pdf.cell(IW - PAD, TITLE_H, title, border=0)
    pdf.set_y(MY + TITLE_H)

    # ── Day headers ────────────────────────────────────────────────────────
    y = pdf.get_y()
    # "Zamestnanec" header
    pdf.set_fill_color(30, 55, 150)
    pdf.rect(MX, y, NAME_W, DHDR_H, 'F')
    pdf.set_text_color(200, 215, 255)
    pdf.set_font('Helvetica', 'B', FS_HDR - 0.5)
    pdf.set_xy(MX + PAD, y)
    pdf.cell(NAME_W - PAD, DHDR_H, 'Zamestnanec', border=0)

    x = MX + NAME_W
    for i, d in enumerate(dates):
        wknd = d.weekday() >= 5
        bg = (45, 70, 180) if wknd else (30, 55, 150)
        pdf.set_fill_color(*bg)
        pdf.rect(x, y, DAY_W, DHDR_H, 'F')
        pdf.set_text_color(200, 215, 255)
        pdf.set_font('Helvetica', 'B', FS_HDR)
        pdf.set_xy(x, y)
        pdf.cell(DAY_W, DHDR_H, _t(f"{day_names[i]} {d.strftime('%d.%m.')}"),
                 border=0, align='C')
        x += DAY_W

    # Outer border for header row
    pdf.set_draw_color(5, 20, 80)
    pdf.rect(MX, y, IW, DHDR_H, 'D')
    pdf.set_y(y + DHDR_H)

    # ── Row drawing ────────────────────────────────────────────────────────
    GRID_COLOR  = ( 90, 105, 140)   # cell border colour – darker for print
    NAME_BG_E   = (225, 230, 248)   # even row name bg
    NAME_BG_O   = (238, 241, 255)   # odd  row name bg
    VOLNO_FG    = (130, 145, 175)
    NOWORK_BG   = (235, 237, 242)

    row_idx = [0]

    def draw_row(row, is_brigada=False):
        emp   = row['employee']
        name  = _t(emp.get('name', ''))
        if is_brigada:
            name += '  B'
        y0    = pdf.get_y()
        even  = (row_idx[0] % 2 == 0)
        n_bg  = NAME_BG_E if even else NAME_BG_O

        pdf.set_draw_color(*GRID_COLOR)

        # Name cell
        pdf.set_fill_color(*n_bg)
        pdf.rect(MX, y0, NAME_W, ROW_H, 'FD')
        pdf.set_text_color(20, 30, 80)
        pdf.set_font('Helvetica', 'B', FS_NAME)
        pdf.set_xy(MX + PAD, y0)
        pdf.cell(NAME_W - PAD, ROW_H, name[:26], border=0)

        # Day cells
        x = MX + NAME_W
        for day in row['days']:
            a     = day.get('assignment')
            wknd  = day.get('is_weekend', False)
            works = day.get('works_on_day', True)

            if not works and not a:
                # Doesn't work this weekday
                pdf.set_fill_color(*NOWORK_BG)
                pdf.rect(x, y0, DAY_W, ROW_H, 'FD')

            elif a is None:
                # Works but free
                cell_bg = (230, 235, 248) if wknd else (250, 251, 255)
                pdf.set_fill_color(*cell_bg)
                pdf.rect(x, y0, DAY_W, ROW_H, 'FD')
                pdf.set_text_color(*VOLNO_FG)
                pdf.set_font('Helvetica', '', FS_SHIFT)
                pdf.set_xy(x, y0)
                pdf.cell(DAY_W, ROW_H, 'volno', border=0, align='C')

            elif a.get('is_absence'):
                atype = a.get('absence_type') or 'jine'
                info  = _ABS.get(atype, _ABS['jine'])
                pdf.set_fill_color(*info['bg'])
                pdf.rect(x, y0, DAY_W, ROW_H, 'FD')
                pdf.set_text_color(*info['fg'])
                pdf.set_font('Helvetica', 'B', FS_TASK)
                pdf.set_xy(x, y0)
                pdf.cell(DAY_W, ROW_H, info['label'], border=0, align='C')

            else:
                # Regular assignment – Google Calendar style
                dept      = _t(a.get('dept_name') or '')
                task      = _t(a.get('task_name') or '')
                shift     = _t(a.get('shift_name') or '')
                vr, vg, vb = _dept_rgb(dept, a.get('dept_color') or '')

                # Coloured cell background – stronger mix for print visibility
                pr, pg, pb = _pastel(vr, vg, vb, mix=0.45 if wknd else 0.38)
                pdf.set_fill_color(pr, pg, pb)
                pdf.rect(x, y0, DAY_W, ROW_H, 'FD')

                # Left accent stripe in vivid colour
                STRIPE = 3.0
                pdf.set_fill_color(vr, vg, vb)
                pdf.rect(x, y0, STRIPE, ROW_H, 'F')

                # Text colours: strong dark for print readability
                dr2, dg2, db2 = _darken(vr, vg, vb, 0.45)

                tx = x + STRIPE + PAD
                tw = DAY_W - STRIPE - PAD

                if TWO_LINE and (task or dept) and shift:
                    # Line 1: dept abbrev + task name (bold)
                    top_h = ROW_H * 0.55
                    bot_h = ROW_H - top_h
                    line1 = f"{dept}  {task}".strip() if dept else task
                    pdf.set_text_color(dr2, dg2, db2)
                    pdf.set_font('Helvetica', 'B', FS_TASK)
                    pdf.set_xy(tx, y0 + (ROW_H - top_h - bot_h) / 2)
                    pdf.cell(tw, top_h, line1, border=0)
                    # Line 2: shift time – slightly lighter but still readable
                    pdf.set_text_color(*_darken(vr, vg, vb, 0.55))
                    pdf.set_font('Helvetica', '', FS_SHIFT)
                    pdf.set_xy(tx, y0 + top_h)
                    pdf.cell(tw, bot_h, shift, border=0)
                else:
                    # Single line
                    parts = []
                    if dept:
                        parts.append(dept)
                    if task:
                        parts.append(task)
                    if shift:
                        parts.append(shift)
                    pdf.set_text_color(dr2, dg2, db2)
                    pdf.set_font('Helvetica', 'B', FS_TASK)
                    pdf.set_xy(tx, y0)
                    pdf.cell(tw, ROW_H, '  '.join(parts), border=0)

            x += DAY_W

        pdf.set_y(y0 + ROW_H)
        row_idx[0] += 1

    # ── Render employees ───────────────────────────────────────────────────
    for row in grid:
        draw_row(row)

    if brigada_grid:
        ys = pdf.get_y()
        pdf.set_fill_color(210, 218, 245)
        pdf.rect(MX, ys, IW, SEP_H, 'F')
        pdf.set_draw_color(*GRID_COLOR)
        pdf.rect(MX, ys, IW, SEP_H, 'D')
        pdf.set_text_color(50, 60, 160)
        pdf.set_font('Helvetica', 'B', 6)
        pdf.set_xy(MX + PAD * 2, ys)
        pdf.cell(IW, SEP_H, 'BRIGADNICI', border=0)
        pdf.set_y(ys + SEP_H)
        for row in brigada_grid:
            draw_row(row, is_brigada=True)

    return bytes(pdf.output())
