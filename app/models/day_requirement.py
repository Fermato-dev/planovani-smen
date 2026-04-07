"""Model pro denní potřeby obsazení (day_requirements)."""
from app.db import get_db


def get_requirements_for_day(plan_id, date):
    """Vrátí seznam požadavků pro daný den jako list Row."""
    db = get_db()
    return db.execute(
        """SELECT dr.id, dr.task_id, dr.min_count, dr.max_count,
                  t.name as task_name, t.department_id,
                  d.name as dept_name, d.color as dept_color, d.sort_order as dept_sort
           FROM day_requirements dr
           JOIN tasks t ON dr.task_id = t.id
           JOIN departments d ON t.department_id = d.id
           WHERE dr.plan_id = ? AND dr.date = ?
           ORDER BY d.sort_order, t.name""",
        (plan_id, date)
    ).fetchall()


def get_requirements_map(plan_id, dates):
    """Vrátí dict {date_str: {task_id: {min_count, max_count}}} pro celý týden."""
    db = get_db()
    date_strs = [d.isoformat() if hasattr(d, 'isoformat') else d for d in dates]
    placeholders = ','.join('?' * len(date_strs))
    rows = db.execute(
        f"""SELECT date, task_id, min_count, max_count
            FROM day_requirements
            WHERE plan_id = ? AND date IN ({placeholders})""",
        [plan_id] + date_strs
    ).fetchall()
    result = {}
    for r in rows:
        if r['date'] not in result:
            result[r['date']] = {}
        result[r['date']][r['task_id']] = {
            'min_count': r['min_count'],
            'max_count': r['max_count'],
        }
    return result


def save_day_requirements(plan_id, date, requirements):
    """Uloží požadavky pro daný den.

    requirements: list of dicts {task_id, min_count, max_count}
    Záznamy s min_count=0 a max_count=None/0 jsou smazány.
    """
    db = get_db()
    # Smazat stávající požadavky pro daný den
    db.execute(
        "DELETE FROM day_requirements WHERE plan_id = ? AND date = ?",
        (plan_id, date)
    )
    # Vložit nové (jen nenulové)
    for req in requirements:
        min_c = int(req.get('min_count') or 0)
        max_c = req.get('max_count')
        max_c = int(max_c) if max_c else None
        if min_c > 0 or (max_c and max_c > 0):
            db.execute(
                """INSERT INTO day_requirements (plan_id, date, task_id, min_count, max_count)
                   VALUES (?, ?, ?, ?, ?)""",
                (plan_id, date, int(req['task_id']), min_c, max_c)
            )
    db.commit()


def clear_day_requirements(plan_id, date):
    """Smaže všechny požadavky pro daný den."""
    db = get_db()
    db.execute(
        "DELETE FROM day_requirements WHERE plan_id = ? AND date = ?",
        (plan_id, date)
    )
    db.commit()
