import logging
from datetime import date, timedelta
from flask import Blueprint, render_template, request, redirect, url_for, flash
from app.models.plan import (
    get_plan, get_all_plans, update_plan_status, delete_plan,
    upsert_assignment, clear_assignment, clear_day, update_email_sent
)
from app.models.day_requirement import (
    get_requirements_for_day, get_requirements_map,
    save_day_requirements, clear_day_requirements
)
from app.models.work_plan import has_entries_map
from app.models.employee import get_employee
from app.models.department import get_all_departments, get_tasks_for_department
from app.models.shift import get_all_shifts
from app.services.planner_service import (
    create_or_get_plan, build_plan_grid, get_staffing_summary,
    get_monday, get_week_dates, ABSENCE_TYPES,
    copy_from_previous_week, refill_from_patterns
)
from app.services.export_service import generate_week_excel
from app.services.email_service import send_schedule_email, is_smtp_configured

logger = logging.getLogger(__name__)

bp = Blueprint('planner', __name__, url_prefix='/planner')

DAY_NAMES = ['Po', 'Út', 'St', 'Čt', 'Pá', 'So', 'Ne']
DAY_NAMES_FULL = ['Pondělí', 'Úterý', 'Středa', 'Čtvrtek', 'Pátek', 'Sobota', 'Neděle']


@bp.route('/')
def index():
    """Show current week or redirect to specific week."""
    week = request.args.get('week')
    if not week:
        monday = get_monday()
        return redirect(url_for('planner.week_view', week_start=monday.isoformat()))
    return redirect(url_for('planner.week_view', week_start=week))


@bp.route('/week/<week_start>')
def week_view(week_start):
    """Main weekly planner view."""
    plan_id, is_new = create_or_get_plan(week_start)
    if is_new:
        flash('Nový plán vytvořen a předvyplněn z výchozích vzorů.', 'success')

    plan = get_plan(plan_id)
    grid, dates = build_plan_grid(plan_id, week_start)
    summary, task_summary = get_staffing_summary(plan_id, dates)
    req_map = get_requirements_map(plan_id, dates)
    work_plan_map = has_entries_map(plan_id, dates)
    departments = get_all_departments()
    shifts = get_all_shifts()

    # Prev/next week navigation
    parts = week_start.split('-')
    ws = date(int(parts[0]), int(parts[1]), int(parts[2]))
    prev_week = (ws - timedelta(weeks=1)).isoformat()
    next_week = (ws + timedelta(weeks=1)).isoformat()
    today_week = get_monday().isoformat()

    # Thursday sending schedule (internal policy: every Thursday send for next 2 weeks)
    # For a week starting Monday: first send = Thursday 11 days before, update = Thursday 4 days before
    today = date.today()
    first_send_thu = ws - timedelta(days=11)   # Thursday 2 weeks before week start
    update_send_thu = ws - timedelta(days=4)   # Thursday 1 week before week start
    first_sent = bool(plan['email_first_sent_at']) if plan['email_first_sent_at'] else False
    update_sent = bool(plan['email_update_sent_at']) if plan['email_update_sent_at'] else False

    # Determine what the next send action should be
    if not first_sent:
        current_send_type = 'first'
    else:
        current_send_type = 'update'

    # Get send status of surrounding weeks (for "which weeks were sent" overview)
    # This Thursday's send covers: next week (week_start+7..+13 from Thu) and week after (week_start+14..+20)
    # Show status for Week+1 and Week+2 from current viewed week
    from app.db import get_db
    db_conn = get_db()
    nearby_weeks = []
    for offset in [-1, 0, 1, 2]:
        nw_start = (ws + timedelta(weeks=offset)).isoformat()
        nw_plan = db_conn.execute(
            "SELECT week_start, week_number, year, email_first_sent_at, email_first_sent_to, "
            "email_update_sent_at, email_update_sent_to FROM weekly_plans WHERE week_start = ?",
            (nw_start,)
        ).fetchone()
        if nw_plan:
            nearby_weeks.append(dict(nw_plan))
        else:
            # Week plan doesn't exist yet
            nw_date = ws + timedelta(weeks=offset)
            nearby_weeks.append({
                'week_start': nw_start,
                'week_number': nw_date.isocalendar()[1],
                'year': nw_date.year,
                'email_first_sent_at': None, 'email_first_sent_to': 0,
                'email_update_sent_at': None, 'email_update_sent_to': 0,
            })

    # Next week info (for two-week email sending display)
    next_ws_date = ws + timedelta(weeks=1)
    next_week_number = next_ws_date.isocalendar()[1]
    next_week_year = next_ws_date.year
    next_week_dates = get_week_dates(next_ws_date.isoformat())

    return render_template('planner/week.html',
                           plan=plan, grid=grid, dates=dates,
                           summary=summary, task_summary=task_summary,
                           req_map=req_map,
                           work_plan_map=work_plan_map,
                           departments=departments,
                           shifts=shifts, day_names=DAY_NAMES,
                           day_names_full=DAY_NAMES_FULL,
                           week_start=week_start,
                           prev_week=prev_week, next_week=next_week,
                           today_week=today_week,
                           absence_types=ABSENCE_TYPES,
                           first_send_thu=first_send_thu,
                           update_send_thu=update_send_thu,
                           first_sent=first_sent,
                           update_sent=update_sent,
                           current_send_type=current_send_type,
                           today=today,
                           nearby_weeks=nearby_weeks,
                           next_week_number=next_week_number,
                           next_week_year=next_week_year,
                           next_week_dates=next_week_dates)


@bp.route('/cell/<int:plan_id>/<int:emp_id>/<cell_date>', methods=['GET'])
def edit_cell(plan_id, emp_id, cell_date):
    """HTMX: return edit form for a single cell."""
    departments = get_all_departments()
    shifts = get_all_shifts()
    from app.db import get_db
    db = get_db()
    assignment = db.execute(
        """SELECT a.*, d.name as dept_name, t.name as task_name, st.name as shift_name
           FROM assignments a
           LEFT JOIN departments d ON a.department_id = d.id
           LEFT JOIN tasks t ON a.task_id = t.id
           LEFT JOIN shift_templates st ON a.shift_template_id = st.id
           WHERE a.plan_id = ? AND a.employee_id = ? AND a.date = ?""",
        (plan_id, emp_id, cell_date)
    ).fetchone()
    return render_template('planner/_cell_edit.html',
                           plan_id=plan_id, emp_id=emp_id, cell_date=cell_date,
                           assignment=assignment, departments=departments,
                           shifts=shifts, absence_types=ABSENCE_TYPES)


@bp.route('/cell/<int:plan_id>/<int:emp_id>/<cell_date>', methods=['POST'])
def save_cell(plan_id, emp_id, cell_date):
    """HTMX: save cell and return updated display."""
    action = request.form.get('action', 'save')

    if action == 'cancel':
        pass  # Just re-render the display without changes
    elif action == 'clear':
        clear_assignment(plan_id, emp_id, cell_date)
    elif action == 'absence':
        absence_type = request.form.get('absence_type', 'jine')
        note = request.form.get('note', '')
        # Partial absence (lékař): also save work assignment for the rest of the day
        shift_id = None
        dept_id = None
        task_id = None
        if absence_type == 'lekar':
            shift_id = request.form.get('partial_shift_id') or None
            dept_id = request.form.get('partial_dept_id') or None
            task_id = request.form.get('partial_task_id') or None
        upsert_assignment(plan_id, emp_id, cell_date,
                          shift_template_id=shift_id, department_id=dept_id,
                          task_id=task_id,
                          is_absence=1, absence_type=absence_type, note=note)
    else:
        shift_id = request.form.get('shift_template_id') or None
        dept_id = request.form.get('department_id') or None
        task_id = request.form.get('task_id') or None
        note = request.form.get('note', '')
        # If nothing selected, treat as clear instead of creating empty record
        if not shift_id and not dept_id and not task_id and not note:
            clear_assignment(plan_id, emp_id, cell_date)
        else:
            upsert_assignment(plan_id, emp_id, cell_date,
                              shift_template_id=shift_id, department_id=dept_id,
                              task_id=task_id, note=note)

    # Return updated cell display
    from app.db import get_db
    db = get_db()
    assignment = db.execute(
        """SELECT a.*, d.name as dept_name, d.color as dept_color,
                  t.name as task_name, st.name as shift_name
           FROM assignments a
           LEFT JOIN departments d ON a.department_id = d.id
           LEFT JOIN tasks t ON a.task_id = t.id
           LEFT JOIN shift_templates st ON a.shift_template_id = st.id
           WHERE a.plan_id = ? AND a.employee_id = ? AND a.date = ?""",
        (plan_id, emp_id, cell_date)
    ).fetchone()
    html = render_template('planner/_cell_display.html',
                           plan_id=plan_id, emp_id=emp_id, cell_date=cell_date,
                           a=assignment)
    # Trigger summary refresh via HTMX (except on cancel)
    if action != 'cancel':
        return html, 200, {'HX-Trigger': 'cellSaved'}
    return html


@bp.route('/summary/<int:plan_id>/<week_start>')
def summary_row(plan_id, week_start):
    """HTMX: return updated staffing summary row."""
    dates = get_week_dates(week_start)
    summary, task_summary = get_staffing_summary(plan_id, dates)
    req_map = get_requirements_map(plan_id, dates)
    return render_template('planner/_summary_row.html',
                           dates=dates, summary=summary,
                           task_summary=task_summary,
                           req_map=req_map)


@bp.route('/requirements/<int:plan_id>/<day_date>', methods=['GET'])
def requirements_panel(plan_id, day_date):
    """HTMX: panel pro nastavení denních potřeb obsazení."""
    departments = get_all_departments()
    from app.db import get_db
    db = get_db()
    # Načteme všechny aktivní práce seskupené pod oddělení
    tasks_by_dept = {}
    for dept in departments:
        tasks = db.execute(
            "SELECT id, name FROM tasks WHERE department_id = ? AND active = 1 ORDER BY name",
            (dept['id'],)
        ).fetchall()
        if tasks:
            tasks_by_dept[dept['id']] = tasks
    # Stávající požadavky pro daný den
    existing = {r['task_id']: r for r in get_requirements_for_day(plan_id, day_date)}
    return render_template('planner/_requirements_panel.html',
                           plan_id=plan_id, day_date=day_date,
                           departments=departments,
                           tasks_by_dept=tasks_by_dept,
                           existing=existing)


@bp.route('/requirements/<int:plan_id>/<day_date>', methods=['POST'])
def requirements_save(plan_id, day_date):
    """HTMX: uloží denní potřeby a vrátí aktualizovaný summary."""
    action = request.form.get('action', 'save')
    if action == 'clear':
        clear_day_requirements(plan_id, day_date)
    else:
        # Sbírám task_id → min/max z formuláře
        requirements = []
        for key, value in request.form.items():
            if key.startswith('min_'):
                task_id = key[4:]
                min_c = value.strip()
                max_c = request.form.get(f'max_{task_id}', '').strip()
                requirements.append({
                    'task_id': task_id,
                    'min_count': min_c or 0,
                    'max_count': max_c or None,
                })
        save_day_requirements(plan_id, day_date, requirements)

    # Vrátíme prázdný response + trigger pro refresh summary
    return '', 200, {'HX-Trigger': 'cellSaved'}


@bp.route('/tasks/<int:dept_id>')
def api_tasks(dept_id):
    """HTMX: return task options for department select."""
    tasks = get_tasks_for_department(dept_id)
    html = '<option value="">—</option>'
    for t in tasks:
        html += f'<option value="{t["id"]}">{t["name"]}</option>'
    return html


@bp.route('/status/<int:plan_id>', methods=['POST'])
def change_status(plan_id):
    """Change plan status (draft/published)."""
    new_status = request.form.get('status', 'draft')
    update_plan_status(plan_id, new_status)
    label = 'publikován' if new_status == 'published' else 'vrácen do konceptu'
    flash(f'Plán {label}.', 'success')
    plan = get_plan(plan_id)
    return redirect(url_for('planner.week_view', week_start=plan['week_start']))


@bp.route('/copy-week/<int:plan_id>', methods=['POST'])
def copy_week(plan_id):
    """Copy assignments from previous week into current plan."""
    plan = get_plan(plan_id)
    if not plan:
        flash('Plán nenalezen.', 'error')
        return redirect(url_for('planner.index'))
    success, msg = copy_from_previous_week(plan_id, plan['week_start'])
    flash(msg, 'success' if success else 'error')
    return redirect(url_for('planner.week_view', week_start=plan['week_start']))


@bp.route('/clear-day/<int:plan_id>/<day_date>', methods=['POST'])
def clear_day_route(plan_id, day_date):
    """Clear all assignments for a specific day."""
    plan = get_plan(plan_id)
    if not plan:
        flash('Plán nenalezen.', 'error')
        return redirect(url_for('planner.index'))
    clear_day(plan_id, day_date)
    flash('Den vymazán.', 'success')
    return redirect(url_for('planner.week_view', week_start=plan['week_start']))


@bp.route('/refill/<int:plan_id>', methods=['POST'])
def refill(plan_id):
    """Clear plan and refill from default patterns + constraints."""
    plan = get_plan(plan_id)
    if not plan:
        flash('Plán nenalezen.', 'error')
        return redirect(url_for('planner.index'))
    refill_from_patterns(plan_id, plan['week_start'])
    flash('Plán přeplněn z výchozích vzorů a omezení.', 'success')
    return redirect(url_for('planner.week_view', week_start=plan['week_start']))


@bp.route('/fill-week/<int:plan_id>/<int:emp_id>', methods=['POST'])
def fill_week(plan_id, emp_id):
    """Fill entire week (Mon-Fri by default) with same shift/dept/task."""
    plan = get_plan(plan_id)
    if not plan:
        flash('Plán nenalezen.', 'error')
        return redirect(url_for('planner.index'))

    shift_id = request.form.get('shift_template_id') or None
    dept_id = request.form.get('department_id') or None
    task_id = request.form.get('task_id') or None
    note = request.form.get('note', '')
    include_weekends = request.form.get('include_weekends') == '1'
    is_absence = request.form.get('action') == 'absence'
    absence_type = request.form.get('absence_type', 'jine')

    dates = get_week_dates(plan['week_start'])
    filled = 0
    for i, d in enumerate(dates):
        # Skip weekends unless explicitly included
        if not include_weekends and i >= 5:
            continue
        if is_absence:
            upsert_assignment(plan_id, emp_id, d.isoformat(),
                              is_absence=1, absence_type=absence_type, note=note)
        else:
            upsert_assignment(plan_id, emp_id, d.isoformat(),
                              shift_template_id=shift_id, department_id=dept_id,
                              task_id=task_id, note=note)
        filled += 1

    emp = get_employee(emp_id)
    emp_name = emp['name'] if emp else '?'
    flash(f'{emp_name}: vyplněno {filled} dní.', 'success')
    return redirect(url_for('planner.week_view', week_start=plan['week_start']))


@bp.route('/send-email/<int:plan_id>', methods=['POST'])
def send_email(plan_id):
    """Send weekly schedule via email to selected employees.

    Always sends TWO weeks: the current viewed week + next week.
    Each week is a separate Excel attachment in the same email.
    """
    plan = get_plan(plan_id)
    if not plan:
        flash('Plán nenalezen.', 'error')
        return redirect(url_for('planner.index'))

    if not is_smtp_configured():
        flash('Email není nakonfigurován. Nastavte Resend API klíč v Nastavení → Email.', 'error')
        return redirect(url_for('planner.week_view', week_start=plan['week_start']))

    send_type = request.form.get('send_type', 'first')
    emp_ids = request.form.getlist('emp_ids')
    if not emp_ids:
        flash('Nebyli vybráni žádní zaměstnanci.', 'warning')
        return redirect(url_for('planner.week_view', week_start=plan['week_start']))

    # --- Week 1 (current) ---
    grid1, dates1 = build_plan_grid(plan_id, plan['week_start'])
    summary1, task_summary1 = get_staffing_summary(plan_id, dates1)
    xlsx1 = generate_week_excel(plan, grid1, dates1, summary1, task_summary1)
    fn1 = f"Plan_smen_{dates1[0].strftime('%d.%m.')}-{dates1[6].strftime('%d.%m.%Y')}.xlsx"

    # --- Week 2 (next week) ---
    parts = plan['week_start'].split('-')
    ws = date(int(parts[0]), int(parts[1]), int(parts[2]))
    next_ws = (ws + timedelta(weeks=1)).isoformat()
    next_plan_id, _ = create_or_get_plan(next_ws)
    next_plan = get_plan(next_plan_id)

    grid2, dates2 = build_plan_grid(next_plan_id, next_ws)
    summary2, task_summary2 = get_staffing_summary(next_plan_id, dates2)
    xlsx2 = generate_week_excel(next_plan, grid2, dates2, summary2, task_summary2)
    fn2 = f"Plan_smen_{dates2[0].strftime('%d.%m.')}-{dates2[6].strftime('%d.%m.%Y')}.xlsx"

    # --- Build attachments list and label ---
    attachments = [(xlsx1, fn1), (xlsx2, fn2)]
    week_label = f"týdny {plan['week_number']}–{next_plan['week_number']}/{plan['year']}"

    sent = 0
    errors = []
    for eid in emp_ids:
        emp = get_employee(int(eid))
        if emp and emp['email']:
            try:
                send_schedule_email(emp['email'], emp['name'], week_label, attachments)
                sent += 1
            except Exception as e:
                logger.error(f"Email failed for {emp['name']} ({emp['email']}): {e}")
                errors.append(emp['name'])

    # Update email tracking for BOTH weeks
    if sent > 0:
        update_email_sent(plan_id, sent, send_type)
        update_email_sent(next_plan_id, sent, send_type)

    if errors:
        flash(f'Odesláno: {sent}. Chyba u: {", ".join(errors)}', 'error')
    else:
        flash(f'Rozpis na 2 týdny odeslán {sent} zaměstnanc{"i" if sent == 1 else "ům"}.', 'success')

    return redirect(url_for('planner.week_view', week_start=plan['week_start']))
