"""CRUD operations for employee constraints (absences, time-off)."""
from datetime import date
from app.db import get_db


def _parse_date(val):
    """Normalize date value from SQLite (may be string or datetime.date)."""
    if isinstance(val, date):
        return val
    if isinstance(val, str):
        parts = val.split('-')
        return date(int(parts[0]), int(parts[1]), int(parts[2]))
    return val


def get_all_constraints(employee_id=None):
    """Get all constraints, optionally filtered by employee."""
    db = get_db()
    if employee_id:
        return db.execute(
            """SELECT c.*, e.name as employee_name
               FROM constraints c
               JOIN employees e ON c.employee_id = e.id
               WHERE c.employee_id = ?
               ORDER BY c.date_from DESC""",
            (employee_id,)
        ).fetchall()
    return db.execute(
        """SELECT c.*, e.name as employee_name
           FROM constraints c
           JOIN employees e ON c.employee_id = e.id
           ORDER BY c.date_from DESC"""
    ).fetchall()


def get_constraint(constraint_id):
    """Get a single constraint by ID."""
    db = get_db()
    return db.execute(
        """SELECT c.*, e.name as employee_name
           FROM constraints c
           JOIN employees e ON c.employee_id = e.id
           WHERE c.id = ?""",
        (constraint_id,)
    ).fetchone()


def create_constraint(employee_id, date_from, date_to, type, subtype='', note='', half_day=0):
    """Create a new constraint. Returns new ID."""
    db = get_db()
    cursor = db.execute(
        """INSERT INTO constraints (employee_id, date_from, date_to, type, subtype, note, half_day)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (employee_id, date_from, date_to, type, subtype, note, half_day)
    )
    db.commit()
    return cursor.lastrowid


def update_constraint(constraint_id, **kwargs):
    """Update constraint fields. Only updates provided kwargs."""
    if not kwargs:
        return
    db = get_db()
    sets = ', '.join(f'{k} = ?' for k in kwargs)
    values = list(kwargs.values()) + [constraint_id]
    db.execute(f"UPDATE constraints SET {sets} WHERE id = ?", values)
    db.commit()


def delete_constraint(constraint_id):
    """Hard delete a constraint."""
    db = get_db()
    db.execute("DELETE FROM constraints WHERE id = ?", (constraint_id,))
    db.commit()


def get_constraints_for_week(week_start, week_end):
    """Get constraints that overlap with the given week range.

    Uses overlap condition: constraint.date_from <= week_end AND constraint.date_to >= week_start
    """
    db = get_db()
    return db.execute(
        """SELECT c.*, e.name as employee_name
           FROM constraints c
           JOIN employees e ON c.employee_id = e.id
           WHERE c.date_from <= ? AND c.date_to >= ?
           ORDER BY c.employee_id, c.date_from""",
        (week_end, week_start)
    ).fetchall()
