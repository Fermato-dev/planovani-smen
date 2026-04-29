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


def get_or_find_plan(week_start):
    """Vrátí plan_id pro daný týden nebo None."""
    db = get_db()
    row = db.execute(
        "SELECT id FROM weekly_plans WHERE week_start = ?", (week_start,)
    ).fetchone()
    return row['id'] if row else None


def create_plan_for_week(week_start):
    """Vytvoří nový weekly_plan a vrátí id."""
    from datetime import date as _date
    parts = week_start.split('-')
    ws = _date(int(parts[0]), int(parts[1]), int(parts[2]))
    iso = ws.isocalendar()
    week_number = iso[1]
    year = iso[0]
    db = get_db()
    cur = db.execute(
        "INSERT INTO weekly_plans (week_start, week_number, year) VALUES (?, ?, ?)",
        (week_start, week_number, year)
    )
    db.commit()
    return cur.lastrowid


# Paleta barev pro kartičky zaměstnanců (generuje se z employee_id)
_BOARD_EMP_COLORS = [
    '5b9bd5',  # ocelová modrá
    '70ad47',  # travní zelená
    'ed7d31',  # teplá oranžová
    'a076c0',  # měkká fialová
    '4ebcd5',  # azurová
    'd95f5f',  # měkká červená
    '58b07c',  # smaragdová
    'f0a500',  # jantar
    '3a87c8',  # královská modrá
    'c47dba',  # mauve
    '60a99b',  # teal
    'e07b54',  # terakota
]


def _emp_color(emp_id):
    """Konzistentní barva zaměstnance z jeho ID (bez sloupce color v DB)."""
    if not emp_id:
        return 'aaaaaa'
    return _BOARD_EMP_COLORS[(int(emp_id) - 1) % len(_BOARD_EMP_COLORS)]


def get_board_assignments(plan_id, dates):
    """Employee-centric board data.
    Vrátí {date_str: {dept_id: [
        {assignment_id, employee_id, name, color, shift_name, note,
         tasks: [{bta_id, task_id, task_name}]}
    ]}}
    """
    db = get_db()
    result = {}
    for d in dates:
        ds = d.isoformat()
        result[ds] = {}

    rows = db.execute(
        """SELECT a.id as assignment_id, a.employee_id, a.department_id,
                  CAST(a.date AS TEXT) as date_str,
                  a.note,
                  e.name,
                  st.name as shift_name
           FROM assignments a
           JOIN employees e ON e.id = a.employee_id
           LEFT JOIN shift_templates st ON st.id = a.shift_template_id
           WHERE a.plan_id = ? AND a.is_absence = 0
             AND a.date IN ({})
           ORDER BY e.name
        """.format(','.join('?' for _ in dates)),
        [plan_id] + [d.isoformat() for d in dates]
    ).fetchall()

    assignment_map = {}  # assignment_id → dict v result

    for r in rows:
        ds = str(r['date_str'])
        dept_id = r['department_id']
        if ds not in result:
            result[ds] = {}
        if dept_id not in result[ds]:
            result[ds][dept_id] = []
        entry = {
            'assignment_id': r['assignment_id'],
            'employee_id': r['employee_id'],
            'name': r['name'],
            'color': _emp_color(r['employee_id']),
            'shift_name': r['shift_name'] or '',
            'note': r['note'] or '',
            'tasks': [],
        }
        result[ds][dept_id].append(entry)
        assignment_map[r['assignment_id']] = entry

    # Přidat tasky z board_task_assignments
    if assignment_map:
        placeholders = ','.join('?' for _ in assignment_map)
        bta_rows = db.execute(
            f"""SELECT bta.id as bta_id, bta.assignment_id, bta.task_id, t.name as task_name
               FROM board_task_assignments bta
               JOIN tasks t ON t.id = bta.task_id
               WHERE bta.assignment_id IN ({placeholders})
               ORDER BY t.name""",
            list(assignment_map.keys())
        ).fetchall()
        for r in bta_rows:
            entry = assignment_map.get(r['assignment_id'])
            if entry:
                entry['tasks'].append({
                    'bta_id': r['bta_id'],
                    'task_id': r['task_id'],
                    'task_name': r['task_name'],
                })
    return result


def get_absent_employees_for_dates(dates):
    """Vrátí {date_str: [{'employee_id':..,'name':..,'color':..}]} pro CELODENNÍ absence.
    Defenzivně — funguje i bez half_day sloupce (migration ještě neproběhla).
    """
    db = get_db()
    # Zjisti, zda sloupec half_day existuje
    c_cols = [r[1] for r in db.execute("PRAGMA table_info(constraints)").fetchall()]
    has_half_day = 'half_day' in c_cols

    half_filter = "AND (c.half_day IS NULL OR c.half_day = 0)" if has_half_day else ""

    result = {}
    for d in dates:
        ds = d.isoformat()
        rows = db.execute(
            f"""SELECT e.id as employee_id, e.name
               FROM constraints c
               JOIN employees e ON e.id = c.employee_id
               WHERE c.date_from <= ? AND c.date_to >= ?
                 {half_filter}
                 AND e.active = 1
               ORDER BY e.name""",
            (ds, ds)
        ).fetchall()
        result[ds] = [{'employee_id': r['employee_id'], 'name': r['name'], 'color': _emp_color(r['employee_id'])} for r in rows]
    return result


def board_assign_employee(plan_id, employee_id, date_str, dept_id):
    """Přiřadí zaměstnance do oddělení na datum (bez konkrétní práce – ta se přidává přes board_add_task).
    Pokud přiřazení již existuje, přesune ho do nového oddělení. Vrátí assignment_id."""
    db = get_db()
    existing = db.execute(
        """SELECT id FROM assignments
           WHERE plan_id = ? AND employee_id = ? AND date = ? AND is_absence = 0""",
        (plan_id, employee_id, date_str)
    ).fetchone()
    if existing:
        db.execute(
            "UPDATE assignments SET department_id=? WHERE id=?",
            (dept_id, existing['id'])
        )
        db.commit()
        return existing['id']
    cur = db.execute(
        """INSERT INTO assignments (plan_id, employee_id, date, department_id, is_absence)
           VALUES (?, ?, ?, ?, 0)""",
        (plan_id, employee_id, date_str, dept_id)
    )
    db.commit()
    return cur.lastrowid


def board_add_task(assignment_id, task_id):
    """Přidá práci k přiřazení zaměstnance. Pokud již existuje, nic nedělá."""
    db = get_db()
    db.execute(
        "INSERT OR IGNORE INTO board_task_assignments (assignment_id, task_id) VALUES (?, ?)",
        (assignment_id, task_id)
    )
    db.commit()


def board_remove_task(bta_id):
    """Odebere jednu práci z přiřazení zaměstnance (zaměstnanec zůstane v oddělení)."""
    db = get_db()
    db.execute("DELETE FROM board_task_assignments WHERE id = ?", (bta_id,))
    db.commit()


def get_available_tasks_for_assignment(assignment_id, dept_id):
    """Vrátí aktivní tasky oddělení, které zatím nejsou přiřazeny k danému assignment_id."""
    db = get_db()
    already = {r[0] for r in db.execute(
        "SELECT task_id FROM board_task_assignments WHERE assignment_id = ?",
        (assignment_id,)
    ).fetchall()}
    all_tasks = db.execute(
        "SELECT id, name FROM tasks WHERE department_id = ? AND active = 1 ORDER BY name",
        (dept_id,)
    ).fetchall()
    return [t for t in all_tasks if t['id'] not in already]


def board_set_note(assignment_id, note):
    """Uloží poznámku k přiřazení zaměstnance."""
    db = get_db()
    db.execute("UPDATE assignments SET note=? WHERE id=?", (note, assignment_id))
    db.commit()


def board_unassign_employee(assignment_id):
    """Smaže přiřazení."""
    db = get_db()
    db.execute("DELETE FROM assignments WHERE id = ?", (assignment_id,))
    db.commit()


def get_available_per_day(dates):
    """Returns dict: date_str -> {total, absent_full, absent_half, available, is_vacation}
    Půldenní absence (half_day=1) se počítají jako 0.5.
    Defenzivní: funguje i bez half_day sloupce.
    """
    db = get_db()
    total = db.execute("SELECT COUNT(*) FROM employees WHERE active=1").fetchone()[0]
    # Zjisti, zda sloupec half_day existuje
    c_cols = [r[1] for r in db.execute("PRAGMA table_info(constraints)").fetchall()]
    has_half_day = 'half_day' in c_cols

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

        if has_half_day:
            # Full-day absences
            full = db.execute(
                """SELECT COUNT(DISTINCT employee_id) FROM constraints
                   WHERE date_from <= ? AND date_to >= ?
                     AND (half_day IS NULL OR half_day = 0)""",
                (ds, ds)
            ).fetchone()[0]
            # Half-day absences
            half = db.execute(
                """SELECT COUNT(DISTINCT employee_id) FROM constraints
                   WHERE date_from <= ? AND date_to >= ?
                     AND half_day = 1""",
                (ds, ds)
            ).fetchone()[0]
        else:
            # half_day column doesn't exist yet — count all constraints as full-day
            full = db.execute(
                """SELECT COUNT(DISTINCT employee_id) FROM constraints
                   WHERE date_from <= ? AND date_to >= ?""",
                (ds, ds)
            ).fetchone()[0]
            half = 0

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
