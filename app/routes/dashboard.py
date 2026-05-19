import calendar as _cal
from datetime import date, timedelta

from flask import Blueprint, render_template, request

from app.models.employee import get_all_employees
from app.models.department import get_all_departments
from app.models.shift import get_all_shifts
from app.models.constraint import get_constraints_for_month, _parse_date

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

    # Employees
    all_emps = get_all_employees(active_only=True, exclude_brigada=False)
    regular_emps = [e for e in all_emps if (e['emp_type'] or 'regular') != 'brigada']
    brigada_emps  = [e for e in all_emps if (e['emp_type'] or 'regular') == 'brigada']

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

    # Day counts — regular employees only
    regular_ids = {e['id'] for e in regular_emps}
    day_counts = {
        d.isoformat(): sum(1 for eid in regular_ids if d.isoformat() in cal.get(eid, {}))
        for d in days
    }

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
        prev_year=prev_year,  prev_month=prev_month,
        next_year=next_year,  next_month=next_month,
    )


@bp.route('/')
def index():
    today = date.today()
    employees   = get_all_employees()
    departments = get_all_departments()
    shifts      = get_all_shifts()
    cal_ctx     = _build_calendar_ctx(today.year, today.month)
    return render_template('dashboard/index.html',
                           employees=employees,
                           departments=departments,
                           shifts=shifts,
                           now=today,
                           **cal_ctx)


@bp.route('/calendar')
def absence_calendar():
    today = date.today()
    year  = int(request.args.get('year',  today.year))
    month = int(request.args.get('month', today.month))
    ctx = _build_calendar_ctx(year, month)
    return render_template('dashboard/_absence_calendar.html', **ctx)
