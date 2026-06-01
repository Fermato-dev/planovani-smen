"""PDF generation using fpdf2 (pure Python, no system dependencies).

Generates A3 landscape weekly schedule PDF that fits on exactly one page.
"""
import logging

logger = logging.getLogger(__name__)

# ── Absence colours (bg, text) ────────────────────────────────────────────────
_ABS_FILL = {
    'dovolena': (254, 243, 199),
    'nemoc':    (254, 226, 226),
    'lekar':    (219, 234, 254),
    'osobni':   (209, 250, 229),
    'nahradni': (237, 233, 254),
    'jine':     (229, 231, 235),
    'svatek':   (254, 249, 195),
}
_ABS_TEXT = {
    'dovolena': (146, 64,  14),
    'nemoc':    (153, 27,  27),
    'lekar':    (30,  64, 175),
    'osobni':   (6,   95,  70),
    'nahradni': (91,  33, 182),
    'jine':     (55,  65,  81),
    'svatek':   (113, 63,  18),
}
_ABS_LABEL = {
    'dovolena': 'Dovolena',
    'nemoc':    'Nemoc',
    'lekar':    'Lekar',
    'osobni':   'Osobni',
    'nahradni': 'Nahradni',
    'jine':     'Jine',
    'svatek':   'Svatek',
}

# Czech diacritics → ASCII (Helvetica built-in = Latin-1 only)
_TRANS = str.maketrans({
    'á': 'a', 'č': 'c', 'ď': 'd', 'é': 'e', 'ě': 'e', 'í': 'i',
    'ľ': 'l', 'ň': 'n', 'ó': 'o', 'ř': 'r', 'š': 's', 'ť': 't',
    'ú': 'u', 'ů': 'u', 'ý': 'y', 'ž': 'z',
    'Á': 'A', 'Č': 'C', 'Ď': 'D', 'É': 'E', 'Ě': 'E', 'Í': 'I',
    'Ľ': 'L', 'Ň': 'N', 'Ó': 'O', 'Ř': 'R', 'Š': 'S', 'Ť': 'T',
    'Ú': 'U', 'Ů': 'U', 'Ý': 'Y', 'Ž': 'Z',
})


def _t(s):
    return str(s).translate(_TRANS) if s else ''


def _hex_rgb(hex_str):
    h = (hex_str or 'D9D9D9').lstrip('#').zfill(6)
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _is_dark(r, g, b):
    """True if colour is dark enough to warrant white text on top."""
    return (r * 299 + g * 587 + b * 114) < 128_000


def generate_week_pdf(plan, grid, brigada_grid, dates, day_names):
    """Return PDF bytes – A3 landscape, one page, coloured dept badges."""
    try:
        from fpdf import FPDF
    except ImportError:
        raise RuntimeError("fpdf2 neni nainstalovano.")

    # ── Page geometry ──────────────────────────────────────────────────────
    PAGE_W, PAGE_H = 420, 297
    MX, MY = 5, 5
    IW = PAGE_W - 2 * MX           # 410 mm
    IH = PAGE_H - 2 * MY           # 287 mm

    TITLE_H = 8
    DHDR_H  = 7
    NAME_W  = IW * 0.135           # ~55 mm
    DAY_W   = (IW - NAME_W) / 7   # ~50 mm

    n_reg  = len(grid)
    n_brig = len(brigada_grid)
    SEP_H  = 4 if brigada_grid else 0
    avail  = IH - TITLE_H - DHDR_H - SEP_H
    n_rows = n_reg + n_brig
    ROW_H  = max(5.0, avail / n_rows) if n_rows else 7

    # Font sizes
    FS_NAME  = max(6.0, min(9.0, ROW_H * 1.3))   # employee name
    FS_TASK  = max(5.5, min(8.5, ROW_H * 1.2))   # task text
    FS_BADGE = max(5.0, min(7.5, ROW_H * 1.0))   # dept badge label
    FS_SHIFT = max(4.5, min(7.0, ROW_H * 0.9))   # shift time (smaller)

    # Dept badge width (fixed fraction of day cell)
    BADGE_W = min(DAY_W * 0.30, 14.0)

    # ── PDF setup ──────────────────────────────────────────────────────────
    pdf = FPDF(orientation='L', unit='mm', format='A3')
    pdf.set_auto_page_break(False)
    pdf.add_page()
    pdf.set_margins(MX, MY, MX)
    pdf.set_y(MY)

    # helper: draw a filled + outlined cell manually
    def rect_cell(x, y, w, h, fill_rgb, text, font_style='', font_size=7,
                  text_rgb=(26, 26, 26), align='L', padding_l=1.5):
        pdf.set_fill_color(*fill_rgb)
        pdf.rect(x, y, w, h, 'F')
        pdf.set_text_color(*text_rgb)
        pdf.set_font('Helvetica', font_style, font_size)
        pdf.set_xy(x + padding_l, y)
        pdf.cell(w - padding_l, h, text, align=align, border=0)

    # ── Title bar ──────────────────────────────────────────────────────────
    pdf.set_fill_color(30, 58, 138)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font('Helvetica', 'B', 11)
    title = (f"Plan smen – tyden {plan['week_number']}/{plan['year']}   "
             f"{dates[0].strftime('%d.%m.')} – {dates[6].strftime('%d.%m.%Y')}")
    pdf.cell(IW, TITLE_H, _t(title), border=0, fill=True)
    pdf.ln(TITLE_H)

    # ── Day-header row ─────────────────────────────────────────────────────
    pdf.set_font('Helvetica', 'B', 7)
    pdf.set_fill_color(30, 58, 138)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(NAME_W, DHDR_H, 'Zamestnanec', border=1, fill=True, align='L')
    for i, d in enumerate(dates):
        pdf.set_fill_color(29, 78, 216 if d.weekday() >= 5 else 30, 64, 175)
        if d.weekday() >= 5:
            pdf.set_fill_color(29, 78, 216)
        else:
            pdf.set_fill_color(30, 64, 175)
        label = f"{_t(day_names[i])} {d.strftime('%d.%m.')}"
        pdf.cell(DAY_W, DHDR_H, label, border=1, fill=True, align='C')
    pdf.ln(DHDR_H)

    # ── Employee row helper ────────────────────────────────────────────────
    row_idx = [0]

    def draw_row(row, is_brigada=False):
        emp    = row['employee']
        name   = _t(emp.get('name', ''))
        if is_brigada:
            name += ' B'

        even   = row_idx[0] % 2 == 0
        row_bg = (245, 247, 250) if even else (255, 255, 255)
        y0     = pdf.get_y()

        # ── Name cell ──
        name_bg = (235, 240, 255) if even else (241, 245, 255)
        rect_cell(MX, y0, NAME_W, ROW_H,
                  fill_rgb=name_bg,
                  text=name[:26],
                  font_style='B', font_size=FS_NAME,
                  text_rgb=(20, 30, 80), padding_l=2)
        pdf.rect(MX, y0, NAME_W, ROW_H, 'D')

        # ── Day cells ──
        x = MX + NAME_W
        for day in row['days']:
            a     = day.get('assignment')
            wknd  = day.get('is_weekend', False)
            works = day.get('works_on_day', True)

            base_bg = (230, 235, 255) if wknd else row_bg

            if not works and not a:
                # doesn't work this weekday
                rect_cell(x, y0, DAY_W, ROW_H,
                          fill_rgb=(240, 243, 247),
                          text='', font_size=FS_TASK,
                          text_rgb=(200, 210, 220))

            elif a is None:
                # scheduled to work but no shift = volno
                rect_cell(x, y0, DAY_W, ROW_H,
                          fill_rgb=base_bg,
                          text='volno', font_size=FS_TASK,
                          text_rgb=(160, 175, 195), align='C')

            elif a.get('is_absence'):
                atype  = a.get('absence_type') or 'jine'
                fill   = _ABS_FILL.get(atype, (229, 231, 235))
                tcol   = _ABS_TEXT.get(atype,  (55,  65,  81))
                label  = _ABS_LABEL.get(atype, 'Jine')
                rect_cell(x, y0, DAY_W, ROW_H,
                          fill_rgb=fill, text=label,
                          font_style='B', font_size=FS_TASK,
                          text_rgb=tcol, align='C')

            else:
                # ── Regular assignment with coloured dept badge ──
                dept       = _t(a.get('dept_name') or '')
                task       = _t(a.get('task_name') or '')
                shift      = _t(a.get('shift_name') or '')
                dept_hex   = a.get('dept_color') or 'D9D9D9'
                dr, dg, db = _hex_rgb(dept_hex)

                # Cell background
                pdf.set_fill_color(*base_bg)
                pdf.rect(x, y0, DAY_W, ROW_H, 'F')

                if dept:
                    # Coloured dept badge (left side of cell)
                    badge_text_col = (255, 255, 255) if _is_dark(dr, dg, db) else (30, 30, 30)
                    pdf.set_fill_color(dr, dg, db)
                    pdf.rect(x, y0, BADGE_W, ROW_H, 'F')
                    pdf.set_text_color(*badge_text_col)
                    pdf.set_font('Helvetica', 'B', FS_BADGE)
                    pdf.set_xy(x, y0)
                    pdf.cell(BADGE_W, ROW_H, dept[:4], align='C', border=0)
                    tx = x + BADGE_W + 1.5
                    tw = DAY_W - BADGE_W - 1.5
                else:
                    tx = x + 1.5
                    tw = DAY_W - 1.5

                # Task name (bold)
                if task:
                    pdf.set_text_color(20, 20, 20)
                    pdf.set_font('Helvetica', 'B', FS_TASK)
                    pdf.set_xy(tx, y0)
                    # Two-line if shift fits: top = task, bottom = shift
                    if shift and ROW_H >= 8:
                        half = ROW_H / 2
                        pdf.cell(tw, half, task, border=0, align='L')
                        pdf.set_text_color(90, 100, 120)
                        pdf.set_font('Helvetica', '', FS_SHIFT)
                        pdf.set_xy(tx, y0 + half)
                        pdf.cell(tw, half, shift, border=0, align='L')
                    else:
                        # Single line: task + shift
                        combined = f'{task}  {shift}'.strip() if shift else task
                        pdf.cell(tw, ROW_H, combined, border=0, align='L')

            # Cell border
            pdf.rect(x, y0, DAY_W, ROW_H, 'D')
            x += DAY_W

        pdf.set_y(y0 + ROW_H)
        row_idx[0] += 1

    # ── Render ────────────────────────────────────────────────────────────
    for row in grid:
        draw_row(row)

    if brigada_grid:
        y_sep = pdf.get_y()
        pdf.set_fill_color(220, 228, 255)
        pdf.rect(MX, y_sep, IW, SEP_H, 'F')
        pdf.set_text_color(50, 40, 160)
        pdf.set_font('Helvetica', 'B', 6.5)
        pdf.set_xy(MX + 2, y_sep)
        pdf.cell(IW, SEP_H, 'BRIGADNICI', border=0)
        pdf.rect(MX, y_sep, IW, SEP_H, 'D')
        pdf.set_y(y_sep + SEP_H)

        for row in brigada_grid:
            draw_row(row, is_brigada=True)

    return bytes(pdf.output())
