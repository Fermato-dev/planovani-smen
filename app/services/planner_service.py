"""Service layer for shift planning - generates weekly plans from default patterns."""
import random
from datetime import date, timedelta
from app.models.plan import (
    create_plan, get_plan_by_week, upsert_assignment,
    get_assignments_for_plan, clear_all_assignments
)
from app.models.employee import get_all_employees, get_default_pattern, get_qualified_tasks, employee_works_on_day
from app.models.constraint import get_constraints_for_week, _parse_date
from app.db import get_db


ABSENCE_TYPES = [
    ('dovolena', 'Dovolená'),
    ('nemoc', 'Nemoc'),
    ('lekar', 'Lékař'),
    ('osobni', 'Osobní volno'),
    ('nahradni', 'Náhradní volno'),
    ('jine', 'Jiné'),
    ('svatek', 'Svátek 🎉'),
]


def get_week_dates(week_start_str):
    """Return list of 7 date objects (Mon-Sun) for given week start."""
    if isinstance(week_start_str, str):
        parts = week_start_str.split('-')
        start = date(int(parts[0]), int(parts[1]), int(parts[2]))
    else:
        start = week_start_str
    return [start + timedelta(days=i) for i in range(7)]


def get_monday(d=None):
    """Get Monday of the current or given date's week."""
    if d is None:
        d = date.today()
    return d - timedelta(days=d.weekday())


def create_or_get_plan(week_start):
    """Get existing plan for week or create new one with auto-filled patterns."""
    if isinstance(week_start, str):
        parts = week_start.split('-')
        ws = date(int(parts[0]), int(parts[1]), int(parts[2]))
    else:
        ws = week_start
        week_start = ws.isoformat()

    existing = get_plan_by_week(week_start)
    if existing:
        return existing['id'], False

    week_number = ws.isocalendar()[1]
    year = ws.isocalendar()[0]
    plan_id = create_plan(week_start, week_number, year)
    dates = get_week_dates(ws)

    # Use shared fill logic: patterns + holidays as svátek + constraints
    _fill_patterns_and_constraints(plan_id, ws, dates)

    return plan_id, True


def build_plan_grid(plan_id, week_start):
    """Build the planning grid data structure: employees × days with assignments."""
    employees = get_all_employees(active_only=True)
    assignments = get_assignments_for_plan(plan_id)
    dates = get_week_dates(week_start)

    # Index assignments by (employee_id, date_string)
    assignment_map = {}
    for a in assignments:
        # Normalize date to string (sqlite may return date object or string)
        d_val = a['date']
        d_str = d_val.isoformat() if hasattr(d_val, 'isoformat') else str(d_val)
        key = (a['employee_id'], d_str)
        assignment_map[key] = dict(a)

    grid = []
    for emp in employees:
        row = {
            'employee': dict(emp),
            'days': []
        }
        for d in dates:
            key = (emp['id'], d.isoformat())
            cell = assignment_map.get(key)
            row['days'].append({
                'date': d,
                'date_str': d.isoformat(),
                'assignment': cell,
                'is_weekend': d.weekday() >= 5,
                'works_on_day': employee_works_on_day(emp, d.weekday())
            })
        grid.append(row)

    return grid, dates


def get_staffing_summary(plan_id, dates):
    """Get staffing counts per department and task per day."""
    from app.models.plan import get_day_summary, get_day_task_summary
    summary = {}
    task_summary = {}
    for d in dates:
        ds = d.isoformat()
        summary[ds] = get_day_summary(plan_id, ds)
        task_summary[ds] = get_day_task_summary(plan_id, ds)
    return summary, task_summary


def _resolve_task_for_pattern(emp_id, pattern_entries, dates):
    """Resolve tasks for pattern entries where dept is set but task is not.

    For each such entry, pick a qualified task using round-robin from a
    shuffled list so the employee rotates through all positions over the week.
    Returns dict: {day_idx: resolved_task_id}.
    """
    resolved = {}

    # Group pattern entries that need task rotation by department
    dept_days = {}  # dept_id -> [day_idx, ...]
    for p in pattern_entries:
        day_idx = p['day_of_week']
        if day_idx < 7 and p['department_id'] and not p['task_id']:
            dept_id = p['department_id']
            dept_days.setdefault(dept_id, []).append(day_idx)

    for dept_id, day_indices in dept_days.items():
        tasks = get_qualified_tasks(emp_id, dept_id)
        if not tasks:
            continue  # No qualified tasks → leave task_id empty
        task_ids = [t['id'] for t in tasks]
        random.shuffle(task_ids)
        # Round-robin: cycle through shuffled tasks
        for i, day_idx in enumerate(sorted(day_indices)):
            resolved[day_idx] = task_ids[i % len(task_ids)]

    return resolved


def _fill_patterns_and_constraints(plan_id, ws, dates):
    """Fill a plan with default patterns and constraints. Reusable core logic.

    When a pattern has department but no task, a random qualified task is
    assigned so employees rotate through all positions they're qualified for.
    Czech public holidays are filled as 'svátek' absence for all employees.
    """
    from app.utils.holidays import get_holidays_for_dates
    holiday_map = get_holidays_for_dates(dates)

    employees = get_all_employees(active_only=True)

    # Pass 1: fill regular pattern days (skip holidays and non-work days)
    for emp in employees:
        pattern = get_default_pattern(emp['id'])
        # Resolve random tasks for dept-only patterns
        task_rotation = _resolve_task_for_pattern(emp['id'], pattern, dates)
        for p in pattern:
            day_idx = p['day_of_week']
            if day_idx < 7:
                d = dates[day_idx]
                if d.isoformat() in holiday_map:
                    continue  # Will be filled as svátek in pass 2
                if not employee_works_on_day(emp, d.weekday()):
                    continue  # Přeskočit den kdy zaměstnanec nepracuje
                task_id = p['task_id'] or task_rotation.get(day_idx)
                upsert_assignment(
                    plan_id=plan_id,
                    employee_id=emp['id'],
                    date=d.isoformat(),
                    shift_template_id=p['shift_template_id'],
                    department_id=p['department_id'],
                    task_id=task_id
                )

    # Pass 2: mark all holidays as svátek absence for ALL active employees
    for d in dates:
        ds = d.isoformat()
        holiday_name = holiday_map.get(ds)
        if holiday_name:
            for emp in employees:
                upsert_assignment(
                    plan_id=plan_id,
                    employee_id=emp['id'],
                    date=ds,
                    shift_template_id=None,
                    department_id=None,
                    task_id=None,
                    is_absence=1,
                    absence_type='svatek',
                    note=holiday_name
                )

    # Pass 3: auto-fill absences from constraints (override svátek if needed)
    # Půldenní absence (half_day=1): zachovej předplněnou práci, jen přidej poznámku.
    # Celodenní absence (half_day=0): přepiš celý assignment.
    from app.db import get_db
    db = get_db()
    week_end = dates[6].isoformat()
    constraints = get_constraints_for_week(ws.isoformat(), week_end)
    for c in constraints:
        c_from = _parse_date(c['date_from'])
        c_to = _parse_date(c['date_to'])
        half_day = c['half_day'] if 'half_day' in c.keys() else 0
        for d in dates:
            if c_from <= d <= c_to:
                if half_day:
                    # Půldenní: přidej jen poznámku k existujícímu přiřazení
                    note_text = c['note'] or ''
                    existing = db.execute(
                        "SELECT id FROM assignments WHERE plan_id=? AND employee_id=? AND date=?",
                        (plan_id, c['employee_id'], d.isoformat())
                    ).fetchone()
                    if existing:
                        db.execute(
                            "UPDATE assignments SET note=? WHERE id=?",
                            (note_text, existing['id'])
                        )
                    else:
                        # Žádné předplněné přiřazení → zapíš jako celodenní absenci
                        upsert_assignment(
                            plan_id=plan_id,
                            employee_id=c['employee_id'],
                            date=d.isoformat(),
                            is_absence=1,
                            absence_type=c['type'],
                            note=note_text
                        )
                else:
                    # Celodenní absence: přepiš vše
                    upsert_assignment(
                        plan_id=plan_id,
                        employee_id=c['employee_id'],
                        date=d.isoformat(),
                        shift_template_id=None,
                        department_id=None,
                        task_id=None,
                        is_absence=1,
                        absence_type=c['type'],
                        note=c['note'] or ''
                    )
    db.commit()


def copy_from_previous_week(target_plan_id, target_week_start):
    """Copy all assignments from previous week's plan into target plan."""
    if isinstance(target_week_start, str):
        parts = target_week_start.split('-')
        ws = date(int(parts[0]), int(parts[1]), int(parts[2]))
    else:
        ws = target_week_start

    prev_monday = ws - timedelta(days=7)
    prev_plan = get_plan_by_week(prev_monday.isoformat())
    if not prev_plan:
        return False, 'Předchozí týden nemá žádný plán.'

    source_assignments = get_assignments_for_plan(prev_plan['id'])
    if not source_assignments:
        return False, 'Předchozí týden je prázdný.'

    target_dates = get_week_dates(ws)
    clear_all_assignments(target_plan_id)

    for a in source_assignments:
        src_date = _parse_date(a['date'])
        day_idx = (src_date - prev_monday).days
        if 0 <= day_idx < 7:
            upsert_assignment(
                plan_id=target_plan_id,
                employee_id=a['employee_id'],
                date=target_dates[day_idx].isoformat(),
                shift_template_id=a['shift_template_id'],
                department_id=a['department_id'],
                task_id=a['task_id'],
                note=a['note'] or '',
                is_absence=a['is_absence'] or 0,
                absence_type=a['absence_type'] or ''
            )

    return True, f'Zkopírováno {len(source_assignments)} přiřazení z týdne {prev_plan["week_number"]}.'


def refill_from_patterns(plan_id, week_start):
    """Clear all assignments and refill from default patterns + constraints."""
    if isinstance(week_start, str):
        parts = week_start.split('-')
        ws = date(int(parts[0]), int(parts[1]), int(parts[2]))
    else:
        ws = week_start

    dates = get_week_dates(ws)
    clear_all_assignments(plan_id)
    _fill_patterns_and_constraints(plan_id, ws, dates)
    return True
