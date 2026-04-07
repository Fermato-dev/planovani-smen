from flask import Blueprint, make_response, abort, render_template
from app.models.plan import get_plan_by_week
from app.models.day_requirement import get_requirements_map
from app.models.shift import get_all_shifts
from app.services.planner_service import build_plan_grid, get_staffing_summary, get_week_dates
from app.services.export_service import generate_week_excel

bp = Blueprint('export', __name__, url_prefix='/export')

DAY_NAMES = ['Po', 'Út', 'St', 'Čt', 'Pá', 'So', 'Ne']


@bp.route('/week/<week_start>')
def export_week(week_start):
    """Download weekly plan as Excel file."""
    plan = get_plan_by_week(week_start)
    if not plan:
        abort(404)

    grid, dates = build_plan_grid(plan['id'], week_start)
    summary, task_summary = get_staffing_summary(plan['id'], dates)

    xlsx_bytes = generate_week_excel(plan, grid, dates, summary, task_summary)

    # Build filename: Plan_smen_02.03.-08.03.2026.xlsx
    date_from = dates[0].strftime('%d.%m.')
    date_to = dates[6].strftime('%d.%m.%Y')
    filename = f'Plan_smen_{date_from}-{date_to}.xlsx'

    response = make_response(xlsx_bytes)
    response.headers['Content-Type'] = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    response.headers['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


@bp.route('/week/<week_start>/print')
def print_week(week_start):
    """Tisková stránka týdenního plánu (pro uložení jako PDF)."""
    plan = get_plan_by_week(week_start)
    if not plan:
        abort(404)

    grid, dates = build_plan_grid(plan['id'], week_start)
    summary, task_summary = get_staffing_summary(plan['id'], dates)
    req_map = get_requirements_map(plan['id'], dates)
    shifts = get_all_shifts()

    return render_template('planner/week_print.html',
                           plan=plan, grid=grid, dates=dates,
                           summary=summary, task_summary=task_summary,
                           req_map=req_map, shifts=shifts,
                           day_names=DAY_NAMES)
