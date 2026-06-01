import calendar as _cal
import colorsys
from datetime import date, timedelta

from flask import Blueprint, render_template, request

from app.models.employee import get_all_employees
from app.models.department import get_all_departments
from app.models.shift import get_all_shifts
from app.models.constraint import get_constraints_for_month, _parse_date
from app.models.plan import get_plan_by_week, get_day_summary, get_day_task_summary
from app.utils.holidays import get_czech_holidays
from app.services.planner_service import get_monday

bp = Blueprint('dashboard', __name__)

MONTH_NAMES_CS = [
    '', 'Leden', 'Únor', 'Březen', 'Duben', 'Květen', 'Červen',
    'Červenec', 'Srpen', 'Září', 'Říjen', 'Listopad', 'Prosinec'
]


def _build_calendar_ctx(year, month):
    """Build template context dict for the absence calendar partial."""
    today = date.today()

    # Clamp month
    if month < 1:
        month = 12; year -= 1
    if month > 12:
        month = 1;  year += 1

    num_days = _cal.monthrange(year, month)[1]
    days = [date(year, month, d) for d in range(1, num_days + 1)]

    # Build cell map: emp_id -> date_str -> {type, half_day, note, id}
    month_start = days[0]
    month_end   = days[-1]
    cal = {}
    for c in get_constraints_for_month(year, month):
        emp_id = c['employee_id']
        d_from = max(_parse_date(c['date_from']), month_start)
        d_to   = min(_parse_date(c['date_to']),   month_end)
        cur = d_from
        while cur <= d_to:
            ds = cur.isoformat()
            if emp_id not in cal:
                cal[emp_id] = {}
            cal[emp_id][ds] = {
                'type':     c['type'] or 'jine',
                'half_day': bool(c['half_day']),
                'note':     c['note'] or '',
                'id':       c['id'],
            }
            cur += timedelta(days=1)

    # Employees — only those with at least one absence this month
    all_emps = get_all_employees(active_only=True, exclude_brigada=False)
    regular_emps = [e for e in all_emps
                    if (e['emp_type'] or 'regular') != 'brigada' and e['id'] in cal]
    brigada_emps  = [e for e in all_emps
                     if (e['emp_type'] or 'regular') == 'brigada' and e['id'] in cal]

    # Day counts — regular employees only
    regular_ids = {e['id'] for e in all_emps if (e['emp_type'] or 'regular') != 'brigada'}
    day_counts = {
        d.isoformat(): sum(1 for eid in regular_ids if d.isoformat() in cal.get(eid, {}))
        for d in days
    }

    # Czech public holidays for the displayed month
    raw_holidays = get_czech_holidays(year)
    # include adjacent years if month spans year boundary (not needed here, but safe)
    holidays = {d.isoformat(): name for d, name in raw_holidays.items()
                if d.month == month and d.year == year}

    # Navigation
    prev_year,  prev_month  = (year - 1, 12) if month == 1  else (year, month - 1)
    next_year,  next_month  = (year + 1,  1) if month == 12 else (year, month + 1)

    return dict(
        year=year, month=month,
        month_name=MONTH_NAMES_CS[month],
        days=days,
        today=today,
        regular_emps=regular_emps,
        brigada_emps=brigada_emps,
        cal=cal,
        day_counts=day_counts,
        holidays=holidays,
        prev_year=prev_year,  prev_month=prev_month,
        next_year=next_year,  next_month=next_month,
    )


def _build_today_staffing(today):
    """Return today's staffing grouped by dept, or None if no plan exists.

    Returns list of dicts:
      {id, name, color, staff_count, tasks: [{name, staff_count, max_staff}, ...]}
    """
    monday = get_monday(today)
    plan = get_plan_by_week(monday.isoformat())
    if not plan:
        return None

    ds = today.isoformat()
    dept_rows = get_day_summary(plan['id'], ds)
    task_rows = get_day_task_summary(plan['id'], ds)

    # Index tasks by dept
    tasks_by_dept = {}
    for t in task_rows:
        tasks_by_dept.setdefault(t['department_id'], []).append(dict(t))

    # Curated UI palette: (hue_degrees, header_hex, body_tint_hex)
    # Covers the full hue wheel with colors that fit the app's design language
    _UI_PALETTE = [
        (  0, '#be123c', '#fff1f2'),   # rose / red
        ( 22, '#c2410c', '#fff7ed'),   # orange
        ( 45, '#a16207', '#fefce8'),   # yellow → dark amber (not muddy brown)
        ( 90, '#15803d', '#f0fdf4'),   # green
        (150, '#0f766e', '#f0fdfa'),   # teal  ← matches app primary
        (200, '#0369a1', '#f0f9ff'),   # sky blue
        (230, '#1d4ed8', '#eff6ff'),   # blue
        (260, '#6d28d9', '#f5f3ff'),   # violet
        (290, '#7e22ce', '#faf5ff'),   # purple
        (320, '#be185d', '#fdf2f8'),   # pink
    ]

    def _css_color(raw):
        """Ensure color has # prefix for CSS. Falls back to teal."""
        if not raw or raw.strip('#').upper() in ('D9D9D9', 'FFFFFF', ''):
            return '#0f766e'
        return raw if raw.startswith('#') else '#' + raw

    def _palette_for(hex_color):
        """Map a DB color to the nearest UI-palette entry by hue distance."""
        h = hex_color.lstrip('#')
        r, g, b = int(h[0:2], 16) / 255.0, int(h[2:4], 16) / 255.0, int(h[4:6], 16) / 255.0
        hue_deg, lightness, sat = colorsys.rgb_to_hls(r, g, b)
        hue_deg = hue_deg * 360  # colorsys gives 0-1

        # If already very dark and saturated (admin picked a proper color) — use it directly
        if lightness < 0.45 and sat > 0.40:
            # Still compute body tint from this hue
            r2, g2, b2 = colorsys.hls_to_rgb(hue_deg / 360, 0.96, max(sat, 0.30))
            body = '#{:02x}{:02x}{:02x}'.format(int(r2 * 255), int(g2 * 255), int(b2 * 255))
            return hex_color, body

        # Find nearest palette entry by hue distance (circular)
        def hue_dist(a, b):
            d = abs(a - b) % 360
            return d if d <= 180 else 360 - d

        best = min(_UI_PALETTE, key=lambda p: hue_dist(hue_deg, p[0]))
        return best[1], best[2]

    result = []
    for d in dept_rows:
        base = _css_color(d['color'])
        header_color, body_color = _palette_for(base)
        result.append({
            'id':           d['id'],
            'name':         d['name'],
            'color':        header_color,
            'color_header': header_color,
            'color_body':   body_color,
            'staff_count':  d['staff_count'],
            'min_staff':    d['min_staff'],
            'max_staff':    d['max_staff'],
            'tasks':        tasks_by_dept.get(d['id'], []),
        })

    # Sort: highest staff_count first (VÝR > EXP > SKL), then by name
    result.sort(key=lambda x: (-x['staff_count'], x['name']))
    return result or None


@bp.route('/')
def index():
    today = date.today()
    employees   = get_all_employees()
    cal_ctx     = _build_calendar_ctx(today.year, today.month)
    today_staffing = _build_today_staffing(today)
    return render_template('dashboard/index.html',
                           employees=employees,
                           now=today,
                           today_staffing=today_staffing,
                           **cal_ctx)


@bp.route('/calendar')
def absence_calendar():
    today = date.today()
    year  = int(request.args.get('year',  today.year))
    month = int(request.args.get('month', today.month))
    ctx = _build_calendar_ctx(year, month)
    return render_template('dashboard/_absence_calendar.html', **ctx)
