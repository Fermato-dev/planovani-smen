"""Routes pro denní plán práce."""
from datetime import datetime
from flask import Blueprint, render_template, request
from app.models.work_plan import (
    get_entries_or_default, save_entries, copy_from_previous_day, get_entries
)

bp = Blueprint('work_plan', __name__, url_prefix='/work-plan')

SECTION_LABELS = {
    'lahvovani': 'Lahvování',
    'priprava': 'Příprava',
}


@bp.route('/<int:plan_id>/<day_date>/<section>', methods=['GET'])
def panel(plan_id, day_date, section):
    """HTMX: vrátí formulář pro plán práce daného dne a sekce."""
    entries, is_default = get_entries_or_default(plan_id, day_date, section)
    return render_template('planner/_work_plan_panel.html',
                           plan_id=plan_id, day_date=day_date,
                           section=section,
                           section_label=SECTION_LABELS.get(section, section),
                           entries=entries,
                           is_default=is_default)


@bp.route('/<int:plan_id>/<day_date>/<section>/save', methods=['POST'])
def save(plan_id, day_date, section):
    """Uloží záznamy plánu práce a vrátí aktualizovaný panel."""
    time_froms = request.form.getlist('time_from[]')
    time_tos = request.form.getlist('time_to[]')
    lines = request.form.getlist('line[]')
    products = request.form.getlist('product[]')
    quantities = request.form.getlist('quantity[]')
    notes = request.form.getlist('note[]')

    entries = []
    for i in range(len(time_froms)):
        entries.append({
            'time_from': time_froms[i] if i < len(time_froms) else '',
            'time_to': time_tos[i] if i < len(time_tos) else '',
            'line': lines[i] if i < len(lines) else '',
            'product': products[i] if i < len(products) else '',
            'quantity': quantities[i] if i < len(quantities) else '',
            'note': notes[i] if i < len(notes) else '',
        })

    save_entries(plan_id, day_date, section, entries)

    # Vrátíme prázdný response + trigger pro zavření modalu
    return '', 200, {'HX-Trigger': 'workPlanSaved'}


@bp.route('/<int:plan_id>/<day_date>/<section>/copy', methods=['POST'])
def copy_prev(plan_id, day_date, section):
    """Zkopíruje záznamy z předchozího dne a vrátí předvyplněný panel (bez uložení)."""
    entries, from_date = copy_from_previous_day(plan_id, day_date, section)
    return render_template('planner/_work_plan_panel.html',
                           plan_id=plan_id, day_date=day_date,
                           section=section,
                           section_label=SECTION_LABELS.get(section, section),
                           entries=entries,
                           is_default=False,
                           copied_from=from_date)


@bp.route('/<int:plan_id>/<day_date>/print')
def print_day(plan_id, day_date):
    """Tisková stránka plánu práce pro daný den (obě sekce)."""
    lahvovani = get_entries(plan_id, day_date, 'lahvovani')
    priprava = get_entries(plan_id, day_date, 'priprava')
    sections = [
        ('lahvovani', 'Lahvování', lahvovani),
        ('priprava', 'Příprava', priprava),
    ]
    now = datetime.now().strftime('%d.%m.%Y %H:%M')
    return render_template('planner/work_plan_print.html',
                           plan_id=plan_id, day_date=day_date,
                           sections=sections, now=now)
