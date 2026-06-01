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

# Czech diacritics → ASCII (fpdf2 built-in Helvetica only supports Latin-1)
_TRANS = str.maketrans({
    'á': 'a', 'č': 'c', 'ď': 'd', 'é': 'e', 'ě': 'e', 'í': 'i',
    'ľ': 'l', 'ň': 'n', 'ó': 'o', 'ř': 'r', 'š': 's', 'ť': 't',
    'ú': 'u', 'ů': 'u', 'ý': 'y', 'ž': 'z',
    'Á': 'A', 'Č': 'C', 'Ď': 'D', 'É': 'E', 'Ě': 'E', 'Í': 'I',
    'Ľ': 'L', 'Ň': 'N', 'Ó': 'O', 'Ř': 'R', 'Š': 'S', 'Ť': 'T',
    'Ú': 'U', 'Ů': 'U', 'Ý': 'Y', 'Ž': 'Z',
})


def _t(s):
    """Transliterate Czech diacritics to ASCII."""
    return str(s).translate(_TRANS) if s else ''


def generate_week_pdf(plan, grid, brigada_grid, dates, day_names):
    """Return PDF bytes for the weekly schedule.

    Args:
        plan:         plan dict  (week_number, year, …)
        grid:         list of regular-employee rows from build_plan_grid
        brigada_grid: list of brigádník rows
        dates:        list of 7 date objects
        day_names:    list of 7 short day-name strings ['Po','Ut',…]
    """
    try:
        from fpdf import FPDF
    except ImportError:
        raise RuntimeError("fpdf2 neni nainstalovano. Pridejte 'fpdf2' do requirements.txt.")

    # ── Page geometry ──────────────────────────────────────────────────────
    PAGE_W, PAGE_H = 420, 297      # A3 landscape mm
    MX, MY = 6, 6                  # margins mm
    IW = PAGE_W - 2 * MX          # inner width  408 mm
    IH = PAGE_H - 2 * MY          # inner height 285 mm

    TITLE_H = 8                    # title bar height
    DHDR_H  = 7                    # day-header row height
    NAME_W  = IW * 0.135          # ~55 mm  name column
    DAY_W   = (IW - NAME_W) / 7  # ~50 mm  each day column

    n_reg  = len(grid)
    n_brig = len(brigada_grid)
    SEP_H  = 4 if brigada_grid else 0
    avail  = IH - TITLE_H - DHDR_H - SEP_H
    n_rows = n_reg + n_brig
    ROW_H  = max(4.5, avail / n_rows) if n_rows else 6
    FS     = max(5.5, min(8.0, ROW_H * 1.45))   # auto font size

    # ── PDF object ─────────────────────────────────────────────────────────
    pdf = FPDF(orientation='L', unit='mm', format='A3')
    pdf.set_auto_page_break(False)
    pdf.add_page()
    pdf.set_margins(MX, MY, MX)
    pdf.set_y(MY)

    # ── Title bar ──────────────────────────────────────────────────────────
    title = (
        f"Plan smen - tyden {plan['week_number']}/{plan['year']}   "
        f"{dates[0].strftime('%d.%m.')} - {dates[6].strftime('%d.%m.%Y')}"
    )
    pdf.set_fill_color(30, 58, 138)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font('Helvetica', 'B', 10)
    pdf.cell(IW, TITLE_H, title, border=0, fill=True)
    pdf.ln(TITLE_H)

    # ── Day-header row ─────────────────────────────────────────────────────
    pdf.set_font('Helvetica', 'B', 7)
    pdf.set_fill_color(30, 58, 138)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(NAME_W, DHDR_H, 'Zamestnanec', border=1, fill=True, align='L')
    for i, d in enumerate(dates):
        if d.weekday() >= 5:
            pdf.set_fill_color(29, 78, 216)
        else:
            pdf.set_fill_color(30, 64, 175)
        label = f"{_t(day_names[i])} {d.strftime('%d.%m.')}"
        pdf.cell(DAY_W, DHDR_H, label, border=1, fill=True, align='C')
    pdf.ln(DHDR_H)

    # ── Employee-row helper ────────────────────────────────────────────────
    row_idx = [0]

    def draw_row(row, is_brigada=False):
        emp     = row['employee']
        name    = _t(emp.get('name', ''))
        if is_brigada:
            name += ' (B)'

        even_bg = (248, 250, 252) if row_idx[0] % 2 == 0 else (255, 255, 255)

        # name cell
        pdf.set_fill_color(*even_bg)
        pdf.set_text_color(26, 26, 26)
        pdf.set_font('Helvetica', 'B', FS)
        pdf.cell(NAME_W, ROW_H, name[:24], border=1, fill=True, align='L')

        for day in row['days']:
            a     = day.get('assignment')
            wknd  = day.get('is_weekend', False)
            works = day.get('works_on_day', True)

            base_bg = (238, 242, 255) if wknd else even_bg

            if not works and not a:
                # employee doesn't work this weekday
                pdf.set_fill_color(241, 245, 249)
                pdf.set_text_color(203, 213, 225)
                pdf.set_font('Helvetica', '', FS)
                pdf.cell(DAY_W, ROW_H, '', border=1, fill=True)

            elif a is None:
                # works today, no assignment = volno
                pdf.set_fill_color(*base_bg)
                pdf.set_text_color(148, 163, 184)
                pdf.set_font('Helvetica', '', FS)
                pdf.cell(DAY_W, ROW_H, 'volno', border=1, fill=True, align='C')

            elif a.get('is_absence'):
                atype = a.get('absence_type') or 'jine'
                pdf.set_fill_color(*_ABS_FILL.get(atype, (229, 231, 235)))
                pdf.set_text_color(*_ABS_TEXT.get(atype, (55, 65, 81)))
                pdf.set_font('Helvetica', 'B', FS)
                pdf.cell(DAY_W, ROW_H,
                         _ABS_LABEL.get(atype, 'Jine'),
                         border=1, fill=True, align='C')
            else:
                # regular work assignment
                pdf.set_fill_color(*base_bg)
                pdf.set_text_color(26, 26, 26)
                pdf.set_font('Helvetica', '', FS - 0.5)
                dept  = _t(a.get('dept_name') or '')
                task  = _t(a.get('task_name') or '')
                shift = _t(a.get('shift_name') or '')
                parts = []
                if dept:
                    parts.append(f'[{dept}]')
                if task:
                    parts.append(task)
                if shift:
                    parts.append(shift)
                pdf.cell(DAY_W, ROW_H, ' '.join(parts), border=1, fill=True, align='L')

        pdf.ln(ROW_H)
        row_idx[0] += 1

    # ── Render rows ────────────────────────────────────────────────────────
    for row in grid:
        draw_row(row)

    if brigada_grid:
        # separator bar
        pdf.set_fill_color(238, 242, 255)
        pdf.set_text_color(55, 48, 163)
        pdf.set_font('Helvetica', 'B', 6)
        pdf.cell(IW, SEP_H, '  BRIGADNICI', border=1, fill=True)
        pdf.ln(SEP_H)

        for row in brigada_grid:
            draw_row(row, is_brigada=True)

    return bytes(pdf.output())
