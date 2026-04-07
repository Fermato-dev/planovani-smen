from app.db import get_db


def get_all_departments(active_only=True):
    db = get_db()
    q = "SELECT * FROM departments"
    if active_only:
        q += " WHERE active = 1"
    q += " ORDER BY sort_order, name"
    return db.execute(q).fetchall()


def get_department(dept_id):
    db = get_db()
    return db.execute("SELECT * FROM departments WHERE id = ?", (dept_id,)).fetchone()


def create_department(name, full_name, color='D9D9D9', min_staff=0, max_staff=99):
    db = get_db()
    db.execute(
        "INSERT INTO departments (name, full_name, color, min_staff, max_staff) VALUES (?, ?, ?, ?, ?)",
        (name, full_name, color, min_staff, max_staff)
    )
    db.commit()


def update_department(dept_id, **kwargs):
    db = get_db()
    fields = []
    values = []
    for key, val in kwargs.items():
        if key in ('name', 'full_name', 'color', 'min_staff', 'max_staff', 'sort_order', 'active', 'work_plan'):
            fields.append(f"{key} = ?")
            values.append(val)
    if fields:
        values.append(dept_id)
        db.execute(f"UPDATE departments SET {', '.join(fields)} WHERE id = ?", values)
        db.commit()


def delete_department(dept_id):
    db = get_db()
    # Clear references in related tables before soft-deleting
    db.execute("UPDATE assignments SET department_id = NULL WHERE department_id = ?", (dept_id,))
    db.execute("UPDATE employee_default_pattern SET department_id = NULL WHERE department_id = ?", (dept_id,))
    db.execute("DELETE FROM employee_qualifications WHERE department_id = ?", (dept_id,))
    # Also nullify task references for tasks belonging to this department
    task_ids = [r['id'] for r in db.execute("SELECT id FROM tasks WHERE department_id = ?", (dept_id,)).fetchall()]
    for tid in task_ids:
        db.execute("UPDATE assignments SET task_id = NULL WHERE task_id = ?", (tid,))
        db.execute("UPDATE employee_default_pattern SET task_id = NULL WHERE task_id = ?", (tid,))
        db.execute("DELETE FROM employee_qualifications WHERE task_id = ?", (tid,))
    db.execute("UPDATE departments SET active = 0 WHERE id = ?", (dept_id,))
    db.commit()


# --- Tasks ---

def get_tasks_for_department(dept_id, active_only=True):
    db = get_db()
    q = "SELECT * FROM tasks WHERE department_id = ?"
    params = [dept_id]
    if active_only:
        q += " AND active = 1"
    q += " ORDER BY name"
    return db.execute(q, params).fetchall()


def get_all_tasks(active_only=True):
    db = get_db()
    q = """SELECT t.*, d.name as dept_name, d.color as dept_color
           FROM tasks t JOIN departments d ON t.department_id = d.id"""
    if active_only:
        q += " WHERE t.active = 1 AND d.active = 1"
    q += " ORDER BY d.sort_order, t.name"
    return db.execute(q).fetchall()


def get_task(task_id):
    db = get_db()
    return db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()


def create_task(department_id, name, min_staff=0, max_staff=99):
    db = get_db()
    db.execute("INSERT INTO tasks (department_id, name, min_staff, max_staff) VALUES (?, ?, ?, ?)",
               (department_id, name, min_staff, max_staff))
    db.commit()


def update_task(task_id, **kwargs):
    db = get_db()
    fields = []
    values = []
    for key, val in kwargs.items():
        if key in ('name', 'department_id', 'active', 'min_staff', 'max_staff'):
            fields.append(f"{key} = ?")
            values.append(val)
    if fields:
        values.append(task_id)
        db.execute(f"UPDATE tasks SET {', '.join(fields)} WHERE id = ?", values)
        db.commit()


def delete_task(task_id):
    db = get_db()
    # Clear references in related tables before deleting
    db.execute("UPDATE assignments SET task_id = NULL WHERE task_id = ?", (task_id,))
    db.execute("UPDATE employee_default_pattern SET task_id = NULL WHERE task_id = ?", (task_id,))
    db.execute("DELETE FROM employee_qualifications WHERE task_id = ?", (task_id,))
    db.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
    db.commit()
