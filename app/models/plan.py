from app.db import get_db


# --- Weekly Plans ---

def get_plan(plan_id):
    db = get_db()
    return db.execute("SELECT * FROM weekly_plans WHERE id = ?", (plan_id,)).fetchone()


def get_plan_by_week(week_start):
    db = get_db()
    return db.execute("SELECT * FROM weekly_plans WHERE week_start = ?", (week_start,)).fetchone()


def get_all_plans(limit=20):
    db = get_db()
    return db.execute(
        "SELECT * FROM weekly_plans ORDER BY week_start DESC LIMIT ?", (limit,)
    ).fetchall()


def create_plan(week_start, week_number, year):
    db = get_db()
    cursor = db.execute(
        "INSERT INTO weekly_plans (week_start, week_number, year) VALUES (?, ?, ?)",
        (week_start, week_number, year)
    )
    db.commit()
    return cursor.lastrowid


def update_plan_status(plan_id, status):
    db = get_db()
    db.execute(
        "UPDATE weekly_plans SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (status, plan_id)
    )
    db.commit()


def delete_plan(plan_id):
    db = get_db()
    db.execute("DELETE FROM weekly_plans WHERE id = ?", (plan_id,))
    db.commit()


def update_email_sent(plan_id, count, send_type='first'):
    """Record that schedule emails were sent for this plan.

    send_type: 'first' = initial preview send (2 weeks ahead),
               'update' = updated schedule send (1 week ahead).
    """
    db = get_db()
    if send_type == 'update':
        db.execute(
            "UPDATE weekly_plans SET email_update_sent_at = CURRENT_TIMESTAMP, email_update_sent_to = ? WHERE id = ?",
            (count, plan_id)
        )
    else:
        db.execute(
            "UPDATE weekly_plans SET email_first_sent_at = CURRENT_TIMESTAMP, email_first_sent_to = ? WHERE id = ?",
            (count, plan_id)
        )
    # Also update legacy columns
    db.execute(
        "UPDATE weekly_plans SET email_sent_at = CURRENT_TIMESTAMP, email_sent_count = ? WHERE id = ?",
        (count, plan_id)
    )
    db.commit()


# --- Assignments ---

def get_assignments_for_plan(plan_id):
    db = get_db()
    return db.execute(
        """SELECT a.*, e.name as emp_name, e.sort_order as emp_sort,
                  d.name as dept_name, d.color as dept_color,
                  t.name as task_name,
                  st.name as shift_name, st.start_time, st.end_time
           FROM assignments a
           JOIN employees e ON a.employee_id = e.id
           LEFT JOIN departments d ON a.department_id = d.id
           LEFT JOIN tasks t ON a.task_id = t.id
           LEFT JOIN shift_templates st ON a.shift_template_id = st.id
           WHERE a.plan_id = ?
           ORDER BY e.sort_order, e.name, a.date""",
        (plan_id,)
    ).fetchall()


def get_assignment(assignment_id):
    db = get_db()
    return db.execute(
        """SELECT a.*, e.name as emp_name,
                  d.name as dept_name, t.name as task_name,
                  st.name as shift_name
           FROM assignments a
           JOIN employees e ON a.employee_id = e.id
           LEFT JOIN departments d ON a.department_id = d.id
           LEFT JOIN tasks t ON a.task_id = t.id
           LEFT JOIN shift_templates st ON a.shift_template_id = st.id
           WHERE a.id = ?""",
        (assignment_id,)
    ).fetchone()


def upsert_assignment(plan_id, employee_id, date, shift_template_id=None,
                      department_id=None, task_id=None, note='',
                      is_absence=0, absence_type=''):
    """Insert or update assignment for employee on date in plan."""
    db = get_db()
    existing = db.execute(
        "SELECT id FROM assignments WHERE plan_id = ? AND employee_id = ? AND date = ?",
        (plan_id, employee_id, date)
    ).fetchone()
    if existing:
        db.execute(
            """UPDATE assignments SET shift_template_id=?, department_id=?, task_id=?,
               note=?, is_absence=?, absence_type=?
               WHERE id = ?""",
            (shift_template_id, department_id, task_id, note, is_absence, absence_type,
             existing['id'])
        )
    else:
        db.execute(
            """INSERT INTO assignments
               (plan_id, employee_id, date, shift_template_id, department_id, task_id,
                note, is_absence, absence_type)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (plan_id, employee_id, date, shift_template_id, department_id, task_id,
             note, is_absence, absence_type)
        )
    db.commit()


def delete_assignment(assignment_id):
    db = get_db()
    db.execute("DELETE FROM assignments WHERE id = ?", (assignment_id,))
    db.commit()


def clear_assignment(plan_id, employee_id, date):
    """Remove assignment for employee on specific date."""
    db = get_db()
    db.execute(
        "DELETE FROM assignments WHERE plan_id = ? AND employee_id = ? AND date = ?",
        (plan_id, employee_id, date)
    )
    db.commit()


def clear_day(plan_id, date):
    """Remove all assignments for a specific day in a plan."""
    db = get_db()
    db.execute(
        "DELETE FROM assignments WHERE plan_id = ? AND date = ?",
        (plan_id, date)
    )
    db.commit()


def clear_all_assignments(plan_id):
    """Remove all assignments for an entire plan."""
    db = get_db()
    db.execute("DELETE FROM assignments WHERE plan_id = ?", (plan_id,))
    db.commit()


def get_day_summary(plan_id, date):
    """Get department staffing counts for a specific day.

    Only shows departments with at least one person assigned (staff_count > 0).
    """
    db = get_db()
    return db.execute(
        """SELECT d.id, d.name, d.color, d.min_staff, d.max_staff,
                  COUNT(a.id) as staff_count
           FROM departments d
           LEFT JOIN assignments a ON a.department_id = d.id
                AND a.plan_id = ? AND a.date = ?
                AND (a.is_absence = 0 OR (a.is_absence = 1 AND a.department_id IS NOT NULL))
           WHERE d.active = 1
           GROUP BY d.id
           HAVING COUNT(a.id) > 0
           ORDER BY d.sort_order""",
        (plan_id, date)
    ).fetchall()


def get_day_task_summary(plan_id, date):
    """Get task-level staffing counts for a specific day.

    Shows all tasks with at least one person assigned (staff_count > 0).
    min_staff is kept for display purposes (green/red indicator) when set.
    """
    db = get_db()
    return db.execute(
        """SELECT t.id, t.name, t.department_id, t.max_staff,
                  d.name as dept_name, d.color as dept_color,
                  COUNT(a.id) as staff_count,
                  COALESCE(
                      (SELECT r.min_staff FROM task_date_requirements r
                       WHERE r.task_id = t.id
                         AND r.date_from <= :date
                         AND (r.date_to IS NULL OR r.date_to >= :date)
                       ORDER BY r.date_from DESC LIMIT 1),
                      t.min_staff
                  ) as min_staff
           FROM tasks t
           JOIN departments d ON t.department_id = d.id
           LEFT JOIN assignments a ON a.task_id = t.id
                AND a.plan_id = :plan_id AND a.date = :date
                AND (a.is_absence = 0 OR (a.is_absence = 1 AND a.task_id IS NOT NULL))
           WHERE t.active = 1 AND d.active = 1
           GROUP BY t.id
           HAVING COUNT(a.id) > 0
           ORDER BY d.sort_order, t.name""",
        {'plan_id': plan_id, 'date': date}
    ).fetchall()
