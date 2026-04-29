import json
from flask import Blueprint, render_template, request, redirect, url_for, flash
from app.models.employee import (
    get_all_employees, get_employee, create_employee, update_employee, delete_employee,
    get_qualifications, set_qualifications, get_default_pattern, set_default_pattern
)
from app.models.department import get_all_departments, get_all_tasks, get_tasks_for_department
from app.models.shift import get_all_shifts

bp = Blueprint('employees', __name__, url_prefix='/employees')

DAY_NAMES = ['Pondělí', 'Úterý', 'Středa', 'Čtvrtek', 'Pátek', 'Sobota', 'Neděle']


@bp.route('/')
def index():
    employees = get_all_employees(active_only=False)
    return render_template('employees/index.html', employees=employees)


@bp.route('/add', methods=['GET', 'POST'])
def add():
    shifts = get_all_shifts()
    departments = get_all_departments()
    tasks = get_all_tasks()
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        default_shift_id = request.form.get('default_shift_id') or None
        note = request.form.get('note', '').strip()
        email = request.form.get('email', '').strip()
        if not name:
            flash('Zadejte jméno zaměstnance.', 'error')
            return render_template('employees/form.html',
                                   shifts=shifts, departments=departments, tasks=tasks)
        emp_id = create_employee(name, default_shift_id, note, email=email)
        # Save qualifications
        _save_qualifications(emp_id)
        flash(f'Zaměstnanec {name} přidán.', 'success')
        return redirect(url_for('employees.detail', emp_id=emp_id))
    return render_template('employees/form.html',
                           shifts=shifts, departments=departments, tasks=tasks)


@bp.route('/<int:emp_id>')
def detail(emp_id):
    employee = get_employee(emp_id)
    if not employee:
        flash('Zaměstnanec nenalezen.', 'error')
        return redirect(url_for('employees.index'))
    qualifications = get_qualifications(emp_id)
    pattern = get_default_pattern(emp_id)
    departments = get_all_departments()
    shifts = get_all_shifts()
    # Build pattern dict keyed by day_of_week
    pattern_dict = {p['day_of_week']: p for p in pattern}
    # JSON for JS pre-population of task selects
    pattern_json = json.dumps({
        str(p['day_of_week']): {
            'task_id': p['task_id'],
            'department_id': p['department_id']
        } for p in pattern if p['department_id']
    })
    return render_template('employees/detail.html',
                           employee=employee, qualifications=qualifications,
                           pattern=pattern_dict, departments=departments,
                           shifts=shifts, day_names=DAY_NAMES,
                           pattern_json=pattern_json)


@bp.route('/<int:emp_id>/edit', methods=['GET', 'POST'])
def edit(emp_id):
    employee = get_employee(emp_id)
    if not employee:
        flash('Zaměstnanec nenalezen.', 'error')
        return redirect(url_for('employees.index'))
    shifts = get_all_shifts()
    departments = get_all_departments()
    tasks = get_all_tasks()
    qualifications = get_qualifications(emp_id)
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        default_shift_id = request.form.get('default_shift_id') or None
        note = request.form.get('note', '').strip()
        email = request.form.get('email', '').strip()
        if not name:
            flash('Zadejte jméno zaměstnance.', 'error')
            return render_template('employees/form.html', employee=employee,
                                   shifts=shifts, departments=departments,
                                   tasks=tasks, qualifications=qualifications)
        # Pracovní dny: checkboxy 0-6, NULL = všechny
        work_days_list = request.form.getlist('work_days')
        work_days = ','.join(sorted(work_days_list)) if work_days_list else None
        update_employee(emp_id, name=name, default_shift_id=default_shift_id, note=note, email=email, work_days=work_days)
        _save_qualifications(emp_id)
        flash(f'Zaměstnanec {name} aktualizován.', 'success')
        return redirect(url_for('employees.detail', emp_id=emp_id))
    return render_template('employees/form.html', employee=employee,
                           shifts=shifts, departments=departments,
                           tasks=tasks, qualifications=qualifications)


@bp.route('/<int:emp_id>/toggle', methods=['POST'])
def toggle(emp_id):
    employee = get_employee(emp_id)
    if employee:
        new_active = 0 if employee['active'] else 1
        update_employee(emp_id, active=new_active)
        status = 'deaktivován' if employee['active'] else 'aktivován'
        flash(f'{employee["name"]} {status}.', 'success')
    return redirect(url_for('employees.index'))


@bp.route('/<int:emp_id>/pattern', methods=['POST'])
def save_pattern(emp_id):
    employee = get_employee(emp_id)
    if not employee:
        flash('Zaměstnanec nenalezen.', 'error')
        return redirect(url_for('employees.index'))
    patterns = []
    for day in range(7):
        shift_id = request.form.get(f'day_{day}_shift') or None
        dept_id = request.form.get(f'day_{day}_dept') or None
        task_id = request.form.get(f'day_{day}_task') or None
        if shift_id or dept_id:
            patterns.append({
                'day_of_week': day,
                'shift_template_id': shift_id,
                'department_id': dept_id,
                'task_id': task_id
            })
    set_default_pattern(emp_id, patterns)
    flash('Výchozí vzor uložen.', 'success')
    return redirect(url_for('employees.detail', emp_id=emp_id))


@bp.route('/api/tasks/<int:dept_id>')
def api_tasks(dept_id):
    """HTMX endpoint: return task options for department."""
    tasks = get_tasks_for_department(dept_id)
    html = '<option value="">-- Práce --</option>'
    for t in tasks:
        html += f'<option value="{t["id"]}">{t["name"]}</option>'
    return html


def _save_qualifications(emp_id):
    """Extract qualifications from form and save."""
    quals = []
    # Checkboxes named qual_DEPTID or qual_DEPTID_TASKID
    for key in request.form:
        if key.startswith('qual_'):
            parts = key.split('_')
            if len(parts) == 2:
                # Department-level: qual_DEPTID
                quals.append((int(parts[1]), None))
            elif len(parts) == 3:
                # Task-level: qual_DEPTID_TASKID
                quals.append((int(parts[1]), int(parts[2])))
    set_qualifications(emp_id, quals)
