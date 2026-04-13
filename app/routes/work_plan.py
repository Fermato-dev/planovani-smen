"""Routes pro denní plán práce."""
from datetime import datetime
from flask import Blueprint, render_template, request
from app.models.work_plan import (
    get_entries_or_default, save_entries, copy_from_previous_day,
    get_entries, get_employees_for_day
)

bp = Blueprint('work_plan', __name__, url_prefix='/work-plan')


@bp.route('/<int:plan_id>/<day_date>', methods=['GET'])
def panel(plan_id, day_date):
    """HTMX: vrátí formulář pro plán práce (obě sekce) daného dne."""
    lahvovani, lah_default = get_entries_or_default(plan_id, day_date, 'lahvovani')
    priprava, prep_default = get_entries_or_default(plan_id, day_date, 'priprava')
    koreni, kor_default = get_entries_or_default(plan_id, day_date, 'koreni')
    employees = get_employees_for_day(plan_id, day_date)
    return render_template('planner/_work_plan_panel.html',
                           plan_id=plan_id, day_date=day_date,
                           lahvovani=lahvovani, priprava=priprava, koreni=koreni,
                           lah_default=lah_default, prep_default=prep_default, kor_default=kor_default,
                           employees=employees,
                           copied_from=None)


@bp.route('/<int:plan_id>/<day_date>/save', methods=['POST'])
def save(plan_id, day_date):
    """Uloží obě sekce a vrátí trigger pro zavření modalu."""
    def collect(prefix):
        return [
            {
                'time_from': tf, 'time_to': tt, 'line': ln,
                'product': pr, 'quantity': qty, 'note': nt,
            }
            for tf, tt, ln, pr, qty, nt in zip(
                request.form.getlist(f'{prefix}time_from[]'),
                request.form.getlist(f'{prefix}time_to[]'),
                request.form.getlist(f'{prefix}line[]'),
                request.form.getlist(f'{prefix}product[]'),
                request.form.getlist(f'{prefix}quantity[]'),
                request.form.getlist(f'{prefix}note[]'),
            )
        ]

    save_entries(plan_id, day_date, 'lahvovani', collect('lah_'))
    save_entries(plan_id, day_date, 'priprava', collect('prep_'))
    save_entries(plan_id, day_date, 'koreni', collect('kor_'))
    return '', 200, {'HX-Trigger': 'workPlanSaved'}


@bp.route('/<int:plan_id>/<day_date>/copy', methods=['POST'])
def copy_prev(plan_id, day_date):
    """Zkopíruje obě sekce z předchozího dne (vrátí předvyplněný panel, neuloží)."""
    lahvovani, lah_from = copy_from_previous_day(plan_id, day_date, 'lahvovani')
    priprava, prep_from = copy_from_previous_day(plan_id, day_date, 'priprava')
    koreni, kor_from = copy_from_previous_day(plan_id, day_date, 'koreni')
    copied_from = lah_from or prep_from or kor_from
    employees = get_employees_for_day(plan_id, day_date)
    return render_template('planner/_work_plan_panel.html',
                           plan_id=plan_id, day_date=day_date,
                           lahvovani=lahvovani, priprava=priprava, koreni=koreni,
                           lah_default=False, prep_default=False, kor_default=False,
                           employees=employees,
                           copied_from=copied_from)


@bp.route('/<int:plan_id>/<day_date>/print')
def print_day(plan_id, day_date):
    """Tisková stránka plánu práce pro daný den."""
    lahvovani, _ = get_entries_or_default(plan_id, day_date, 'lahvovani')
    priprava, _ = get_entries_or_default(plan_id, day_date, 'priprava')
    koreni, _ = get_entries_or_default(plan_id, day_date, 'koreni')
    employees = get_employees_for_day(plan_id, day_date)
    sections = [
        ('lahvovani', 'Lahvování', lahvovani),
        ('priprava', 'Příprava', priprava),
        ('koreni', 'Koření', koreni),
    ]
    now = datetime.now().strftime('%d.%m.%Y %H:%M')

    # Česky formátované datum pro nadpis
    _months = ['', 'ledna', 'února', 'března', 'dubna', 'května', 'června',
               'července', 'srpna', 'září', 'října', 'listopadu', 'prosince']
    _days_cs = ['Pondělí', 'Úterý', 'Středa', 'Čtvrtek', 'Pátek', 'Sobota', 'Neděle']
    try:
        _dt = datetime.strptime(day_date, '%Y-%m-%d')
        day_date_formatted = f'{_days_cs[_dt.weekday()]} {_dt.day}. {_months[_dt.month]} {_dt.year}'
    except Exception:
        day_date_formatted = day_date

    return render_template('planner/work_plan_print.html',
                           plan_id=plan_id, day_date=day_date,
                           day_date_formatted=day_date_formatted,
                           sections=sections, employees=employees, now=now)
