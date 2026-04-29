"""Model for company-wide vacations."""
from app.db import get_db


def get_all_company_vacations():
    db = get_db()
    return db.execute(
        "SELECT * FROM company_vacations ORDER BY date_from"
    ).fetchall()


def get_company_vacations_for_week(dates):
    """Return vacations that overlap with any of the given dates."""
    if not dates:
        return []
    db = get_db()
    date_from = min(dates).isoformat()
    date_to = max(dates).isoformat()
    return db.execute(
        """SELECT * FROM company_vacations
           WHERE date_from <= ? AND date_to >= ?
           ORDER BY date_from""",
        (date_to, date_from)
    ).fetchall()


def get_vacation_days_map(dates):
    """Return {date_str: vacation_name} for dates covered by any company vacation."""
    vacations = get_company_vacations_for_week(dates)
    result = {}
    for vac in vacations:
        vac_from = vac['date_from']
        vac_to = vac['date_to']
        for d in dates:
            ds = d.isoformat()
            if vac_from <= ds <= vac_to:
                result[ds] = vac['name']
    return result


def create_company_vacation(name, date_from, date_to):
    db = get_db()
    db.execute(
        "INSERT INTO company_vacations (name, date_from, date_to) VALUES (?, ?, ?)",
        (name, date_from, date_to)
    )
    db.commit()


def delete_company_vacation(vacation_id):
    db = get_db()
    db.execute("DELETE FROM company_vacations WHERE id = ?", (vacation_id,))
    db.commit()


def update_company_vacation(vacation_id, name, date_from, date_to):
    db = get_db()
    db.execute(
        "UPDATE company_vacations SET name=?, date_from=?, date_to=? WHERE id=?",
        (name, date_from, date_to, vacation_id)
    )
    db.commit()
