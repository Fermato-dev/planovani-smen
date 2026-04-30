from app.db import get_db


def get_all_shifts():
    db = get_db()
    return db.execute("SELECT * FROM shift_templates ORDER BY is_default DESC, start_time").fetchall()


def get_shift(shift_id):
    db = get_db()
    return db.execute("SELECT * FROM shift_templates WHERE id = ?", (shift_id,)).fetchone()


def get_default_shift():
    db = get_db()
    return db.execute("SELECT * FROM shift_templates WHERE is_default = 1").fetchone()


def create_shift(name, start_time, end_time, is_default=0):
    db = get_db()
    if is_default:
        db.execute("UPDATE shift_templates SET is_default = 0")
    db.execute(
        "INSERT INTO shift_templates (name, start_time, end_time, is_default) VALUES (?, ?, ?, ?)",
        (name, start_time, end_time, is_default)
    )
    db.commit()


def update_shift(shift_id, **kwargs):
    db = get_db()
    fields = []
    values = []
    for key, val in kwargs.items():
        if key in ('name', 'start_time', 'end_time', 'is_default'):
            fields.append(f"{key} = ?")
            values.append(val)
    if kwargs.get('is_default'):
        db.execute("UPDATE shift_templates SET is_default = 0")
    if fields:
        values.append(shift_id)
        db.execute(f"UPDATE shift_templates SET {', '.join(fields)} WHERE id = ?", values)
        db.commit()


def delete_shift(shift_id):
    db = get_db()
    # Clear references in related tables before deleting
    cur = db.execute("UPDATE assignments SET shift_template_id = NULL WHERE shift_template_id = ?", (shift_id,))
    cleared_assignments = cur.rowcount
    db.execute("UPDATE employee_default_pattern SET shift_template_id = NULL WHERE shift_template_id = ?", (shift_id,))
    db.execute("UPDATE employees SET default_shift_id = NULL WHERE default_shift_id = ?", (shift_id,))
    db.execute("DELETE FROM shift_templates WHERE id = ?", (shift_id,))
    db.commit()
    return {'cleared_assignments': cleared_assignments}
