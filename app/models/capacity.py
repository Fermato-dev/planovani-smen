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


def create_block_type(category, name, sort_order=0, department_id=None):
    db = get_db()
    db.execute(
        "INSERT INTO capacity_block_types (category, name, sort_order, department_id) VALUES (?, ?, ?, ?)",
        (category, name, sort_order, department_id)
    )
    db.commit()


def update_block_type(block_id, department_id):
    """Update the linked department for a block type."""
    db = get_db()
    db.execute(
        "UPDATE capacity_block_types SET department_id=? WHERE id=?",
        (department_id if department_id else None, block_id)
    )
    db.commit()


def delete_block_type(block_id):
    db = get_db()
    db.execute("DELETE FROM capacity_block_types WHERE id=?", (block_id,))
    db.execute("DELETE FROM capacity_entries WHERE block_type_id=?", (block_id,))
    db.commit()


def get_entries_for_week(week_start):
    """Returns:
      fixed_demand: {(date_str, block_type_id): count}  — manually saved overrides
      special:      {date_str: [{id, name, count}]}
    """
    db = get_db()
    rows = db.execute(
        "SELECT * FROM capacity_entries WHERE week_start=?",
        (week_start,)
    ).fetchall()
    fixed_demand = {}
    special = {}
    for r in rows:
        if r['category'] in ('fixed', 'demand') and r['block_type_id']:
            fixed_demand[(r['date'], r['block_type_id'])] = r['count']
        elif r['category'] == 'special':
            ds = r['date']
            if ds not in special:
                special[ds] = []
            special[ds].append({'id': r['id'], 'name': r['name'], 'count': r['count']})
    return fixed_demand, special


def get_planner_counts(week_start, dates, fixed_types):
    """Auto-count from planner for block types linked to a department.
    Returns {(date_str, block_type_id): count}
    Only for fixed types that have department_id set.
    """
    db = get_db()
    result = {}
    for bt in fixed_types:
        dept_id = bt['department_id'] if bt['department_id'] else None
        if not dept_id:
            continue
        for d in dates:
            ds = d.isoformat()
            row = db.execute(
                """SELECT COUNT(DISTINCT a.employee_id) as cnt
                   FROM assignments a
                   JOIN weekly_plans p ON a.plan_id = p.id
                   WHERE p.week_start = ?
                     AND a.date = ?
                     AND a.department_id = ?
                     AND a.is_absence = 0""",
                (week_start, ds, dept_id)
            ).fetchone()
            result[(ds, bt['id'])] = row['cnt'] if row else 0
    return result


def save_entry(week_start, date_str, category, block_type_id, count):
    """Upsert a fixed/demand entry (manual override)."""
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


def clear_entry(week_start, date_str, block_type_id):
    """Remove a manual override so planner auto-count takes effect again."""
    db = get_db()
    db.execute(
        "DELETE FROM capacity_entries WHERE week_start=? AND date=? AND block_type_id=?",
        (week_start, date_str, block_type_id)
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
    """Returns dict: date_str -> {total, absent_full, absent_half, available, is_vacation}
    Půldenní absence (half_day=1) se počítají jako 0.5.
    """
    db = get_db()
    total = db.execute("SELECT COUNT(*) FROM employees WHERE active=1").fetchone()[0]
    result = {}
    for d in dates:
        ds = d.isoformat()

        # Check company vacation first
        on_vacation = db.execute(
            "SELECT COUNT(*) FROM company_vacations WHERE date_from <= ? AND date_to >= ?",
            (ds, ds)
        ).fetchone()[0]

        if on_vacation > 0:
            result[ds] = {
                'total': total, 'absent_full': total, 'absent_half': 0,
                'absent_display': total, 'available': 0, 'is_vacation': True
            }
            continue

        # Full-day absences (half_day = 0 or column doesn't exist yet)
        full = db.execute(
            """SELECT COUNT(DISTINCT employee_id) FROM constraints
               WHERE date_from <= ? AND date_to >= ?
                 AND (half_day IS NULL OR half_day = 0)""",
            (ds, ds)
        ).fetchone()[0]

        # Half-day absences (half_day = 1)
        half = db.execute(
            """SELECT COUNT(DISTINCT employee_id) FROM constraints
               WHERE date_from <= ? AND date_to >= ?
                 AND half_day = 1""",
            (ds, ds)
        ).fetchone()[0]

        # Effective absence = full + 0.5 * half
        effective_absent = full + half * 0.5
        available = max(0.0, total - effective_absent)

        # Display string for absent (e.g. "3" or "2,5")
        absent_display = effective_absent
        result[ds] = {
            'total': total,
            'absent_full': full,
            'absent_half': half,
            'absent_display': absent_display,
            'available': available,
            'is_vacation': False,
        }
    return result
