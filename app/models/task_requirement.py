from app.db import get_db


def get_all_requirements():
    """Get all task date requirements, newest date_from first."""
    db = get_db()
    return db.execute(
        """SELECT r.id, r.task_id, r.date_from, r.date_to, r.min_staff, r.note,
                  t.name as task_name, d.name as dept_name, d.color as dept_color
           FROM task_date_requirements r
           JOIN tasks t ON t.id = r.task_id
           JOIN departments d ON d.id = t.department_id
           ORDER BY r.date_from DESC, t.name"""
    ).fetchall()


def get_requirement(req_id):
    db = get_db()
    return db.execute(
        "SELECT * FROM task_date_requirements WHERE id = ?", (req_id,)
    ).fetchone()


def create_requirement(task_id, date_from, date_to, min_staff, note=''):
    db = get_db()
    db.execute(
        """INSERT INTO task_date_requirements (task_id, date_from, date_to, min_staff, note)
           VALUES (?, ?, ?, ?, ?)""",
        (task_id, date_from, date_to or None, int(min_staff), note)
    )
    db.commit()


def update_requirement(req_id, task_id, date_from, date_to, min_staff, note=''):
    db = get_db()
    db.execute(
        """UPDATE task_date_requirements
           SET task_id=?, date_from=?, date_to=?, min_staff=?, note=?
           WHERE id=?""",
        (task_id, date_from, date_to or None, int(min_staff), note, req_id)
    )
    db.commit()


def delete_requirement(req_id):
    db = get_db()
    db.execute("DELETE FROM task_date_requirements WHERE id = ?", (req_id,))
    db.commit()
