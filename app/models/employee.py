from app.db import get_db


def get_all_employees(active_only=True):
    db = get_db()
    q = """SELECT e.*, st.name as shift_name, st.start_time, st.end_time
           FROM employees e
           LEFT JOIN shift_templates st ON e.default_shift_id = st.id"""
    if active_only:
        q += " WHERE e.active = 1"
    q += " ORDER BY e.sort_order, e.name"
    return db.execute(q).fetchall()


def get_employee(emp_id):
    db = get_db()
    return db.execute(
        """SELECT e.*, st.name as shift_name
           FROM employees e LEFT JOIN shift_templates st ON e.default_shift_id = st.id
           WHERE e.id = ?""",
        (emp_id,)
    ).fetchone()


def find_employee_by_name(name):
    db = get_db()
    return db.execute("SELECT * FROM employees WHERE name = ?", (name.strip(),)).fetchone()


def create_employee(name, default_shift_id=None, note='', email=''):
    db = get_db()
    cursor = db.execute(
        "INSERT INTO employees (name, default_shift_id, note, email) VALUES (?, ?, ?, ?)",
        (name.strip(), default_shift_id, note, email.strip() if email else '')
    )
    db.commit()
    return cursor.lastrowid


def update_employee(emp_id, **kwargs):
    db = get_db()
    fields = []
    values = []
    for key, val in kwargs.items():
        if key in ('name', 'default_shift_id', 'active', 'note', 'email', 'sort_order', 'work_days', 'emp_type'):
            fields.append(f"{key} = ?")
            values.append(val)
    if fields:
        values.append(emp_id)
        db.execute(f"UPDATE employees SET {', '.join(fields)} WHERE id = ?", values)
        db.commit()


def delete_employee(emp_id):
    db = get_db()
    db.execute("UPDATE employees SET active = 0 WHERE id = ?", (emp_id,))
    db.commit()


def hard_delete_employee(emp_id):
    """Natvrdo smaže zaměstnance i všechna jeho data (assignments, constraints, vzory, kvalifikace)."""
    db = get_db()
    # Nejprve smaž board_task_assignments navázané přes assignments
    db.execute(
        """DELETE FROM board_task_assignments
           WHERE assignment_id IN (SELECT id FROM assignments WHERE employee_id = ?)""",
        (emp_id,)
    )
    db.execute("DELETE FROM assignments WHERE employee_id = ?", (emp_id,))
    db.execute("DELETE FROM constraints WHERE employee_id = ?", (emp_id,))
    db.execute("DELETE FROM employee_qualifications WHERE employee_id = ?", (emp_id,))
    db.execute("DELETE FROM employee_default_pattern WHERE employee_id = ?", (emp_id,))
    db.execute("DELETE FROM employees WHERE id = ?", (emp_id,))
    db.commit()


def parse_work_days(work_days_str):
    """Vrátí set čísel dnů (0=Po … 6=Ne) ze stringu 'work_days'. None → všechny dny."""
    if not work_days_str:
        return None  # NULL = pracuje každý den
    try:
        return {int(x.strip()) for x in work_days_str.split(',') if x.strip().isdigit()}
    except Exception:
        return None


def employee_works_on_day(emp, weekday):
    """Vrátí True pokud zaměstnanec pracuje v daný den týdne (0=Po…6=Ne)."""
    work_days = parse_work_days(emp['work_days'] if 'work_days' in emp.keys() else None)
    if work_days is None:
        return True
    return weekday in work_days


# --- Qualifications ---

def get_qualifications(emp_id):
    db = get_db()
    return db.execute(
        """SELECT eq.*, d.name as dept_name, t.name as task_name
           FROM employee_qualifications eq
           JOIN departments d ON eq.department_id = d.id
           LEFT JOIN tasks t ON eq.task_id = t.id
           WHERE eq.employee_id = ?
           ORDER BY d.sort_order, t.name""",
        (emp_id,)
    ).fetchall()


def set_qualifications(emp_id, dept_task_pairs):
    """Set all qualifications for employee. dept_task_pairs = [(dept_id, task_id|None), ...]"""
    db = get_db()
    db.execute("DELETE FROM employee_qualifications WHERE employee_id = ?", (emp_id,))
    for dept_id, task_id in dept_task_pairs:
        db.execute(
            "INSERT INTO employee_qualifications (employee_id, department_id, task_id) VALUES (?, ?, ?)",
            (emp_id, dept_id, task_id)
        )
    db.commit()


def is_qualified(emp_id, dept_id, task_id=None):
    """Check if employee is qualified for department/task."""
    db = get_db()
    # Check department-level qualification (task_id IS NULL means qualified for whole dept)
    row = db.execute(
        "SELECT 1 FROM employee_qualifications WHERE employee_id = ? AND department_id = ? AND task_id IS NULL",
        (emp_id, dept_id)
    ).fetchone()
    if row:
        return True
    if task_id:
        row = db.execute(
            "SELECT 1 FROM employee_qualifications WHERE employee_id = ? AND department_id = ? AND task_id = ?",
            (emp_id, dept_id, task_id)
        ).fetchone()
        return row is not None
    return False


def get_qualified_tasks(emp_id, dept_id):
    """Get list of tasks the employee is qualified for in given department.

    - If employee has department-level qualification (task_id IS NULL),
      returns ALL active tasks in the department.
    - Otherwise returns only specifically qualified tasks.
    """
    db = get_db()
    # Check for department-level qualification first
    dept_qual = db.execute(
        """SELECT 1 FROM employee_qualifications
           WHERE employee_id = ? AND department_id = ? AND task_id IS NULL""",
        (emp_id, dept_id)
    ).fetchone()
    if dept_qual:
        # Qualified for entire department → all active tasks
        return db.execute(
            "SELECT * FROM tasks WHERE department_id = ? AND active = 1 ORDER BY name",
            (dept_id,)
        ).fetchall()
    else:
        # Only specific tasks
        return db.execute(
            """SELECT t.* FROM tasks t
               JOIN employee_qualifications eq
                    ON eq.task_id = t.id AND eq.department_id = t.department_id
               WHERE eq.employee_id = ? AND eq.department_id = ? AND t.active = 1
               ORDER BY t.name""",
            (emp_id, dept_id)
        ).fetchall()


# --- Brigádníci: dostupnost ---

def get_availabilities_for_employee(emp_id, from_date=None):
    """Vrátí záznamy dostupnosti brigádníka, od dnešního data nebo od zadaného data."""
    db = get_db()
    if from_date:
        return db.execute(
            "SELECT * FROM employee_availabilities WHERE employee_id=? AND date >= ? ORDER BY date",
            (emp_id, from_date)
        ).fetchall()
    return db.execute(
        "SELECT * FROM employee_availabilities WHERE employee_id=? ORDER BY date",
        (emp_id,)
    ).fetchall()


def add_availability(emp_id, date, time_from='', time_to='', note=''):
    """Přidá záznam dostupnosti brigádníka. Přepíše existující pro stejný den."""
    db = get_db()
    db.execute(
        """INSERT INTO employee_availabilities (employee_id, date, time_from, time_to, note, status)
           VALUES (?,?,?,?,?,'available')
           ON CONFLICT(employee_id, date) DO UPDATE SET
               time_from=excluded.time_from, time_to=excluded.time_to,
               note=excluded.note, status='available'""",
        (emp_id, date, time_from, time_to, note)
    )
    db.commit()


def delete_availability(avail_id):
    db = get_db()
    db.execute("DELETE FROM employee_availabilities WHERE id=?", (avail_id,))
    db.commit()


def update_availability_status(avail_id, status):
    """Nastaví stav dostupnosti: 'available', 'confirmed', 'not_needed'."""
    if status not in ('available', 'confirmed', 'not_needed'):
        return
    db = get_db()
    db.execute("UPDATE employee_availabilities SET status=? WHERE id=?", (status, avail_id))
    db.commit()


def get_availabilities_for_date(date_str):
    """Vrátí brigádníky dostupné v konkrétní den (status != not_needed)."""
    db = get_db()
    return db.execute(
        """SELECT ea.id as avail_id, ea.employee_id, ea.time_from, ea.time_to,
                  ea.status, ea.note, e.name
           FROM employee_availabilities ea
           JOIN employees e ON e.id = ea.employee_id
           WHERE ea.date = ? AND ea.status != 'not_needed' AND e.active = 1
           ORDER BY ea.status DESC, e.name""",
        (date_str,)
    ).fetchall()


# --- Default Pattern ---

def get_default_pattern(emp_id):
    db = get_db()
    return db.execute(
        """SELECT edp.*, d.name as dept_name, t.name as task_name,
                  st.name as shift_name, st.start_time, st.end_time
           FROM employee_default_pattern edp
           LEFT JOIN departments d ON edp.department_id = d.id
           LEFT JOIN tasks t ON edp.task_id = t.id
           LEFT JOIN shift_templates st ON edp.shift_template_id = st.id
           WHERE edp.employee_id = ?
           ORDER BY edp.day_of_week""",
        (emp_id,)
    ).fetchall()


def set_default_pattern(emp_id, patterns):
    """Set default weekly pattern. patterns = [{day_of_week, shift_template_id, department_id, task_id}, ...]"""
    db = get_db()
    db.execute("DELETE FROM employee_default_pattern WHERE employee_id = ?", (emp_id,))
    for p in patterns:
        db.execute(
            """INSERT INTO employee_default_pattern
               (employee_id, day_of_week, shift_template_id, department_id, task_id)
               VALUES (?, ?, ?, ?, ?)""",
            (emp_id, p['day_of_week'], p.get('shift_template_id'),
             p.get('department_id'), p.get('task_id'))
        )
    db.commit()
