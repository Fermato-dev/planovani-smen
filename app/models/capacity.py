from app.db import get_db


def get_block_types(category=None):
    db = get_db()
    if category:
        return db.execute(
            "SELECT * FROM capacity_block_types WHERE category=? AND active=1 ORDER BY sort_order, name",
            (category,)
        ).fetchall()
    return db.execute(
        "SELECT * FROM capacity_block_types WHERE active=1 ORDER BY category, sort_order, name"
    ).fetchall()


def get_all_block_types():
    db = get_db()
    return db.execute(
        "SELECT * FROM capacity_block_types ORDER BY category, sort_order, name"
    ).fetchall()


def create_block_type(category, name, sort_order=0):
    db = get_db()
    db.execute(
        "INSERT INTO capacity_block_types (category, name, sort_order) VALUES (?, ?, ?)",
        (category, name, sort_order)
    )
    db.commit()


def delete_block_type(block_id):
    db = get_db()
    db.execute("DELETE FROM capacity_block_types WHERE id=?", (block_id,))
    db.execute("DELETE FROM capacity_entries WHERE block_type_id=?", (block_id,))
    db.commit()


def get_entries_for_week(week_start):
    """Returns dict keyed by (date_str, block_type_id) for fixed/demand entries,
    and list for special entries."""
    db = get_db()
    rows = db.execute(
        "SELECT * FROM capacity_entries WHERE week_start=?",
        (week_start,)
    ).fetchall()
    fixed_demand = {}  # (date_str, block_type_id) -> count
    special = {}  # date_str -> list of {id, name, count}
    for r in rows:
        if r['category'] in ('fixed', 'demand') and r['block_type_id']:
            fixed_demand[(r['date'], r['block_type_id'])] = r['count']
        elif r['category'] == 'special':
            ds = r['date']
            if ds not in special:
                special[ds] = []
            special[ds].append({'id': r['id'], 'name': r['name'], 'count': r['count']})
    return fixed_demand, special


def save_entry(week_start, date_str, category, block_type_id, count):
    """Upsert a fixed/demand entry."""
    db = get_db()
    existing = db.execute(
        "SELECT id FROM capacity_entries WHERE week_start=? AND date=? AND block_type_id=?",
        (week_start, date_str, block_type_id)
    ).fetchone()
    if existing:
        db.execute("UPDATE capacity_entries SET count=? WHERE id=?", (count, existing['id']))
    else:
        db.execute(
            "INSERT INTO capacity_entries (week_start, date, category, block_type_id, count) VALUES (?,?,?,?,?)",
            (week_start, date_str, category, block_type_id, count)
        )
    db.commit()


def add_special_task(week_start, date_str, name, count):
    db = get_db()
    db.execute(
        "INSERT INTO capacity_entries (week_start, date, category, name, count) VALUES (?,?,?,?,?)",
        (week_start, date_str, 'special', name, count)
    )
    db.commit()


def delete_entry(entry_id):
    db = get_db()
    db.execute("DELETE FROM capacity_entries WHERE id=?", (entry_id,))
    db.commit()


def get_available_per_day(dates):
    """Returns dict: date_str -> {'total': N, 'absent': N, 'available': N, 'is_vacation': bool}"""
    db = get_db()
    total = db.execute("SELECT COUNT(*) FROM employees WHERE active=1").fetchone()[0]
    result = {}
    for d in dates:
        ds = d.isoformat()
        absent = db.execute(
            "SELECT COUNT(DISTINCT employee_id) FROM constraints WHERE date_from <= ? AND date_to >= ?",
            (ds, ds)
        ).fetchone()[0]
        on_vacation = db.execute(
            "SELECT COUNT(*) FROM company_vacations WHERE date_from <= ? AND date_to >= ?",
            (ds, ds)
        ).fetchone()[0]
        if on_vacation > 0:
            result[ds] = {'total': total, 'absent': total, 'available': 0, 'is_vacation': True}
        else:
            result[ds] = {'total': total, 'absent': absent, 'available': max(0, total - absent), 'is_vacation': False}
    return result
