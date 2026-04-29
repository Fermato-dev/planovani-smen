import logging
from datetime import date, timedelta
from flask import Blueprint, render_template, request, redirect, url_for, flash, make_response

logger = logging.getLogger(__name__)
from app.services.planner_service import get_monday, get_week_dates
from app.models.capacity import (
    get_block_types, get_entries_for_week, save_entry, clear_entry,
    add_special_task, delete_entry, get_available_per_day,
    get_planner_counts,
    get_or_find_plan, create_plan_for_week,
    get_board_assignments, get_absent_employees_for_dates,
    board_assign_employee, board_unassign_employee,
)
from app.models.department import get_all_departments
from app.models.employee import get_all_employees
from app.utils.holidays import get_holidays_for_dates
from app.models.company_vacation import get_vacation_days_map

bp = Blueprint('capacity', __name__, url_prefix='/capacity')

DAY_NAMES = ['Po', 'Ut', 'St', 'Ct', 'Pa', 'So', 'Ne']
DAY_NAMES_CZ = ['Po', 'Út', 'St', 'Čt', 'Pá', 'So', 'Ne']


@bp.route('/')
def index():
    monday = get_monday()
    return redirect(url_for('capacity.board_index'))


# ── Board view ────────────────────────────────────────────────────────────────

@bp.route('/board')
def board_index():
    monday = get_monday()
    return redirect(url_for('capacity.board_view', week_start=monday.isoformat()))


@bp.route('/board/<week_start>')
def board_view(week_start):
    parts = week_start.split('-')
    ws = date(int(parts[0]), int(parts[1]), int(parts[2]))
    ws = ws - timedelta(days=ws.weekday())
    week_start = ws.isoformat()

    all_dates = get_week_dates(week_start)
    dates = all_dates[:5]  # Po–Pá only

    prev_week = (ws - timedelta(weeks=1)).isoformat()
    next_week = (ws + timedelta(weeks=1)).isoformat()
    today_week = get_monday().isoformat()

    holiday_map = get_holidays_for_dates(dates)
    vacation_map = get_vacation_days_map(dates)

    # Plan
    try:
        plan_id = get_or_find_plan(week_start)
        if plan_id is None:
            plan_id = create_plan_for_week(week_start)
    except Exception:
        logger.exception("board_view: chyba při hledání/vytváření plánu")
        raise

    # Departments split by work_plan (defensive – work_plan migration may not have run yet)
    try:
        all_depts = get_all_departments(active_only=True)
        vyroba_depts = []
        expedice_depts = []
        for d in all_depts:
            try:
                wp = d['work_plan']
            except (IndexError, KeyError):
                wp = 1  # default: výroba
            if wp == 0:
                expedice_depts.append(d)
            else:
                vyroba_depts.append(d)
    except Exception:
        logger.exception("board_view: chyba při načítání oddělení")
        raise

    # Board assignments
    try:
        board = get_board_assignments(plan_id, dates)
    except Exception:
        logger.exception("board_view: chyba v get_board_assignments")
        raise

    # Absences
    try:
        absent = get_absent_employees_for_dates(dates)
    except Exception:
        logger.exception("board_view: chyba v get_absent_employees_for_dates")
        absent = {d.isoformat(): [] for d in dates}

    # Unassigned: active employees who have no assignment and no full-day absence that day
    try:
        all_emps = get_all_employees(active_only=True)
        unassigned = {}
        for d in dates:
            ds = d.isoformat()
            absent_ids = {e['employee_id'] for e in absent.get(ds, [])}
            assigned_ids = set()
            for dept_assignments in board.get(ds, {}).values():
                for a in dept_assignments:
                    assigned_ids.add(a['employee_id'])
            unassigned[ds] = [
                {'employee_id': e['id'], 'name': e['name'], 'color': e['color'] or 'aaaaaa'}
                for e in all_emps
                if e['id'] not in assigned_ids and e['id'] not in absent_ids
            ]
    except Exception:
        logger.exception("board_view: chyba při výpočtu nepřiřazených")
        raise

    return render_template(
        'capacity/board.html',
        week_start=week_start,
        dates=dates,
        prev_week=prev_week,
        next_week=next_week,
        today_week=today_week,
        plan_id=plan_id,
        vyroba_depts=vyroba_depts,
        expedice_depts=expedice_depts,
        board=board,
        absent=absent,
        unassigned=unassigned,
        holiday_map=holiday_map,
        vacation_map=vacation_map,
        day_names=DAY_NAMES_CZ,
    )


@bp.route('/board/add-panel/<week_start>/<date_str>/<int:dept_id>')
def board_add_panel(week_start, date_str, dept_id):
    plan_id = get_or_find_plan(week_start)
    if plan_id is None:
        plan_id = create_plan_for_week(week_start)

    # Already assigned on this day (any dept)
    from app.db import get_db
    db = get_db()
    assigned_rows = db.execute(
        """SELECT DISTINCT employee_id FROM assignments
           WHERE plan_id = ? AND date = ? AND is_absence = 0""",
        (plan_id, date_str)
    ).fetchall()
    assigned_ids = {r['employee_id'] for r in assigned_rows}

    # Full-day absences on this day
    absent_rows = db.execute(
        """SELECT DISTINCT employee_id FROM constraints
           WHERE date_from <= ? AND date_to >= ?
             AND (half_day IS NULL OR half_day = 0)""",
        (date_str, date_str)
    ).fetchall()
    absent_ids = {r['employee_id'] for r in absent_rows}

    all_emps = get_all_employees(active_only=True)
    employees = [e for e in all_emps if e['id'] not in assigned_ids and e['id'] not in absent_ids]

    return render_template(
        'capacity/_board_add_panel.html',
        employees=employees,
        week_start=week_start,
        plan_id=plan_id,
        date_str=date_str,
        dept_id=dept_id,
    )


@bp.route('/board/assign', methods=['POST'])
def board_assign():
    week_start = request.form.get('week_start', '')
    plan_id = request.form.get('plan_id', type=int)
    employee_id = request.form.get('employee_id', type=int)
    date_str = request.form.get('date_str', '')
    dept_id = request.form.get('dept_id', type=int)

    if plan_id and employee_id and date_str and dept_id:
        board_assign_employee(plan_id, employee_id, date_str, dept_id)

    return redirect(url_for('capacity.board_view', week_start=week_start))


@bp.route('/board/unassign/<int:assignment_id>', methods=['POST'])
def board_unassign(assignment_id):
    week_start = request.form.get('week_start', '')
    board_unassign_employee(assignment_id)
    return redirect(url_for('capacity.board_view', week_start=week_start))


@bp.route('/week/<week_start>')
def week_view(week_start):
    parts = week_start.split('-')
    ws = date(int(parts[0]), int(parts[1]), int(parts[2]))
    # Snap to Monday
    ws = ws - timedelta(days=ws.weekday())
    week_start = ws.isoformat()

    dates = get_week_dates(week_start)
    prev_week = (ws - timedelta(weeks=1)).isoformat()
    next_week = (ws + timedelta(weeks=1)).isoformat()
    today_week = get_monday().isoformat()

    fixed_types = get_block_types('fixed')
    demand_types = get_block_types('demand')
    fixed_demand, special = get_entries_for_week(week_start)
    available = get_available_per_day(dates)
    holiday_map = get_holidays_for_dates(dates)
    vacation_map = get_vacation_days_map(dates)
    # Auto-počty z plánovače pro bloky napojené na oddělení
    planner_counts = get_planner_counts(week_start, dates, fixed_types)

    return render_template(
        'capacity/week.html',
        week_start=week_start,
        dates=dates,
        prev_week=prev_week,
        next_week=next_week,
        today_week=today_week,
        fixed_types=fixed_types,
        demand_types=demand_types,
        fixed_demand=fixed_demand,
        planner_counts=planner_counts,
        special=special,
        available=available,
        holiday_map=holiday_map,
        vacation_map=vacation_map,
        day_names=DAY_NAMES_CZ,
    )


@bp.route('/save', methods=['POST'])
def save():
    week_start = request.form.get('week_start', '')
    date_str = request.form.get('date', '')
    block_type_id = request.form.get('block_type_id', '')
    count = request.form.get('count', '0')
    category = request.form.get('category', 'fixed')

    try:
        count_int = int(count) if count else 0
        block_id_int = int(block_type_id)
        save_entry(week_start, date_str, category, block_id_int, count_int)
    except (ValueError, Exception):
        return '', 400


@bp.route('/clear-override', methods=['POST'])
def clear_override():
    """Smaže manuální přepis — vrátí se auto-hodnota z plánovače."""
    week_start = request.form.get('week_start', '')
    date_str = request.form.get('date', '')
    block_type_id = request.form.get('block_type_id', '')
    try:
        clear_entry(week_start, date_str, int(block_type_id))
    except (ValueError, Exception):
        return '', 400

    return '', 204


@bp.route('/special/<week_start>/<date_str>')
def special_panel(week_start, date_str):
    _, special = get_entries_for_week(week_start)
    tasks = special.get(date_str, [])
    return render_template(
        'capacity/_special_panel.html',
        week_start=week_start,
        date_str=date_str,
        tasks=tasks,
    )


@bp.route('/special/<week_start>/<date_str>/add', methods=['POST'])
def special_add(week_start, date_str):
    name = request.form.get('name', '').strip()
    count = request.form.get('count', '0')
    if name:
        try:
            add_special_task(week_start, date_str, name, int(count))
        except ValueError:
            pass

    _, special = get_entries_for_week(week_start)
    tasks = special.get(date_str, [])
    return render_template(
        'capacity/_special_panel.html',
        week_start=week_start,
        date_str=date_str,
        tasks=tasks,
    )


@bp.route('/special/<int:entry_id>/delete', methods=['POST'])
def special_delete(entry_id):
    week_start = request.form.get('week_start', '')
    date_str = request.form.get('date_str', '')
    delete_entry(entry_id)

    _, special = get_entries_for_week(week_start)
    tasks = special.get(date_str, [])
    return render_template(
        'capacity/_special_panel.html',
        week_start=week_start,
        date_str=date_str,
        tasks=tasks,
    )
