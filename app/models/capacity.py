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


def sync_board_from_planner(plan_id, dates):
    """Přetáhne existující přiřazení z plánu směn (assignments.task_id) do board struktur.
    Idempotentní — INSERT OR IGNORE, bezpečné volat při každém načtení boardu.
    """
    db = get_db()
    date_strs = [d.isoformat() for d in dates]
    ph = ','.join('?' for _ in dates)

    rows = db.execute(
        f"""SELECT a.id as assignment_id, a.task_id, CAST(a.date AS TEXT) as ds
            FROM assignments a
            WHERE a.plan_id = ? AND a.is_absence = 0
              AND a.task_id IS NOT NULL
              AND a.date IN ({ph})""",
        [plan_id] + date_strs
    ).fetchall()

    for r in rows:
        db.execute(
            "INSERT OR IGNORE INTO board_day_tasks (plan_id, date, task_id) VALUES (?,?,?)",
            (plan_id, r['ds'], r['task_id'])
        )
        db.execute(
            "INSERT OR IGNORE INTO board_task_assignments (assignment_id, task_id) VALUES (?,?)",
            (r['assignment_id'], r['task_id'])
        )
    if rows:
        db.commit()


def get_board_assignments(plan_id, dates):
    """Task-centric board s dynamickým seznamem prací per den.
    Vrátí {date_str: {dept_id: {task_id: {
        'task_name': str,
        'bdt_id': int or None,
        'employees': [{bta_id, assignment_id, employee_id, name, color, shift_name, note}]
    }}}}
    Zahrnuje i práce z board_day_tasks bez přiřazených zaměstnanců (prázdné řádky).
    """
    db = get_db()
    date_strs = [d.isoformat() for d in dates]
    ph = ','.join('?' for _ in dates)

    result = {ds: {} for ds in date_strs}

    # 1. Načíst dynamický seznam prací pro každý den
    bdt_rows = db.execute(
        f"""SELECT bdt.id as bdt_id, CAST(bdt.date AS TEXT) as ds,
                   bdt.task_id, t.name as task_name, t.department_id
            FROM board_day_tasks bdt
            JOIN tasks t ON t.id = bdt.task_id
            WHERE bdt.plan_id = ? AND bdt.date IN ({ph})
            ORDER BY t.name""",
        [plan_id] + date_strs
    ).fetchall()

    for r in bdt_rows:
        ds = str(r['ds'])
        dept_id = r['department_id']
        task_id = r['task_id']
        result.setdefault(ds, {}).setdefault(dept_id, {})
        if task_id not in result[ds][dept_id]:
            result[ds][dept_id][task_id] = {
                'task_name': r['task_name'],
                'bdt_id': r['bdt_id'],
                'employees': [],
            }

    # 2. Načíst zaměstnance přiřazené k pracem
    emp_rows = db.execute(
        f"""SELECT bta.id as bta_id, bta.task_id,
                   a.id as assignment_id, a.employee_id, a.department_id,
                   CAST(a.date AS TEXT) as ds,
                   a.note, e.name,
                   st.name as shift_name
            FROM board_task_assignments bta
            JOIN assignments a ON a.id = bta.assignment_id
            JOIN employees e ON e.id = a.employee_id
            LEFT JOIN shift_templates st ON st.id = a.shift_template_id
            WHERE a.plan_id = ? AND a.is_absence = 0 AND a.date IN ({ph})
            ORDER BY e.name""",
        [plan_id] + date_strs
    ).fetchall()

    for r in emp_rows:
        ds = str(r['ds'])
        dept_id = r['department_id']
        task_id = r['task_id']
        result.setdefault(ds, {}).setdefault(dept_id, {})
        if task_id not in result[ds][dept_id]:
            # Práce je přiřazena zaměstnanci ale není v board_day_tasks — přidej ji
            t = db.execute("SELECT name FROM tasks WHERE id=?", (task_id,)).fetchone()
            result[ds][dept_id][task_id] = {
                'task_name': t['name'] if t else f'#{task_id}',
                'bdt_id': None,
                'employees': [],
            }
        result[ds][dept_id][task_id]['employees'].append({
            'bta_id': r['bta_id'],
            'assignment_id': r['assignment_id'],
            'employee_id': r['employee_id'],
            'name': r['name'],
            'color': _emp_color(r['employee_id']),
            'shift_name': r['shift_name'] or '',
            'note': r['note'] or '',
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
        # Vrátíme VŠECHNY absence (celodenní i půldenní) s příznakem half_day
        rows = db.execute(
            f"""SELECT e.id as employee_id, e.name, c.note, c.type as absence_type,
                       COALESCE(c.half_day, 0) as half_day
               FROM constraints c
               JOIN employees e ON e.id = c.employee_id
               WHERE c.date_from <= ? AND c.date_to >= ?
                 AND e.active = 1
               ORDER BY COALESCE(c.half_day, 0), e.name""",
            (ds, ds)
        ).fetchall()
        result[ds] = [
            {
                'employee_id': r['employee_id'],
                'name': r['name'],
                'color': _emp_color(r['employee_id']),
                'note': r['note'] or '',
                'absence_type': r['absence_type'] or '',
                'half_day': bool(r['half_day']),
            }
            for r in rows
        ]
    return result


def board_assign_to_task(plan_id, employee_id, date_str, task_id):
    """Přiřadí zaměstnance ke konkrétní práci na den.
    1. Najde/vytvoří assignment; nastaví department_id + task_id → propisuje se do plánu směn
    2. Přidá task do board_day_tasks (zajistí viditelný řádek)
    3. Přidá board_task_assignments záznam
    Vrátí assignment_id.
    """
    db = get_db()
    task = db.execute("SELECT department_id FROM tasks WHERE id=?", (task_id,)).fetchone()
    if not task:
        return None
    dept_id = task['department_id']

    existing = db.execute(
        "SELECT id FROM assignments WHERE plan_id=? AND employee_id=? AND date=? AND is_absence=0",
        (plan_id, employee_id, date_str)
    ).fetchone()
    if existing:
        assignment_id = existing['id']
        # Aktualizuj department i task_id → propisuje se do plánu směn
        db.execute(
            "UPDATE assignments SET department_id=?, task_id=? WHERE id=?",
            (dept_id, task_id, assignment_id)
        )
    else:
        cur = db.execute(
            """INSERT INTO assignments
               (plan_id, employee_id, date, department_id, task_id, is_absence)
               VALUES (?,?,?,?,?,0)""",
            (plan_id, employee_id, date_str, dept_id, task_id)
        )
        assignment_id = cur.lastrowid

    db.execute(
        "INSERT OR IGNORE INTO board_day_tasks (plan_id, date, task_id) VALUES (?,?,?)",
        (plan_id, date_str, task_id)
    )
    db.execute(
        "INSERT OR IGNORE INTO board_task_assignments (assignment_id, task_id) VALUES (?,?)",
        (assignment_id, task_id)
    )
    db.commit()
    return assignment_id


def board_remove_task(bta_id):
    """Odebere zaměstnance z konkrétní práce.
    - Pokud zbývají jiné board-práce, aktualizuje assignments.task_id na první zbývající.
    - Pokud žádná board-práce nezbývá:
        * má-li zaměstnanec nastavenou směnu → zachová assignment, jen vymaže task_id
        * nemá-li směnu → smaže celý assignment (vrátí se do nepřiřazených)
    """
    db = get_db()
    bta = db.execute(
        "SELECT bta.assignment_id, bta.task_id FROM board_task_assignments bta WHERE bta.id=?",
        (bta_id,)
    ).fetchone()
    if not bta:
        return
    assignment_id = bta['assignment_id']

    db.execute("DELETE FROM board_task_assignments WHERE id=?", (bta_id,))

    remaining = db.execute(
        "SELECT task_id FROM board_task_assignments WHERE assignment_id=? LIMIT 1",
        (assignment_id,)
    ).fetchone()

    if remaining:
        # Ještě má jiné board-práce → propíše první zbývající do plánu směn
        db.execute(
            "UPDATE assignments SET task_id=? WHERE id=?",
            (remaining['task_id'], assignment_id)
        )
    else:
        # Žádná board-práce nezbývá
        row = db.execute(
            "SELECT shift_template_id FROM assignments WHERE id=?", (assignment_id,)
        ).fetchone()
        if row and row['shift_template_id']:
            # Má směnu → zachovej assignment, vymaž task a poznámku z nástěnky
            db.execute(
                "UPDATE assignments SET task_id=NULL, department_id=NULL, note='' WHERE id=?",
                (assignment_id,)
            )
        else:
            # Bez směny → celý assignment pryč (vrátí se do nepřiřazených)
            db.execute("DELETE FROM assignments WHERE id=?", (assignment_id,))

    db.commit()


def board_add_day_task(plan_id, date_str, task_id):
    """Přidá práci do viditelného seznamu pro daný den (prázdný řádek bez zaměstnanců)."""
    db = get_db()
    db.execute(
        "INSERT OR IGNORE INTO board_day_tasks (plan_id, date, task_id) VALUES (?,?,?)",
        (plan_id, date_str, task_id)
    )
    db.commit()


def board_remove_day_task(bdt_id):
    """Odebere práci ze dne a všechna přiřazení zaměstnanců k ní na tento den."""
    db = get_db()
    bdt = db.execute("SELECT plan_id, date, task_id FROM board_day_tasks WHERE id=?", (bdt_id,)).fetchone()
    if not bdt:
        return
    # Najdi a smaž bta záznamy i potenciálně osiřelé assignments
    bta_rows = db.execute(
        """SELECT bta.id, bta.assignment_id FROM board_task_assignments bta
           JOIN assignments a ON a.id = bta.assignment_id
           WHERE a.plan_id=? AND a.date=? AND bta.task_id=?""",
        (bdt['plan_id'], bdt['date'], bdt['task_id'])
    ).fetchall()
    for row in bta_rows:
        db.execute("DELETE FROM board_task_assignments WHERE id=?", (row['id'],))
        remaining = db.execute(
            "SELECT COUNT(*) FROM board_task_assignments WHERE assignment_id=?", (row['assignment_id'],)
        ).fetchone()[0]
        if remaining == 0:
            db.execute("DELETE FROM assignments WHERE id=?", (row['assignment_id'],))
    db.execute("DELETE FROM board_day_tasks WHERE id=?", (bdt_id,))
    db.commit()


def get_tasks_not_on_day(plan_id, date_str, dept_id):
    """Vrátí aktivní tasky oddělení, které ještě nejsou v board_day_tasks pro daný den."""
    db = get_db()
    already = {r[0] for r in db.execute(
        """SELECT bdt.task_id FROM board_day_tasks bdt
           JOIN tasks t ON t.id = bdt.task_id
           WHERE bdt.plan_id=? AND bdt.date=? AND t.department_id=?""",
        (plan_id, date_str, dept_id)
    ).fetchall()}
    all_tasks = db.execute(
        "SELECT id, name FROM tasks WHERE department_id=? AND active=1 ORDER BY name",
        (dept_id,)
    ).fetchall()
    return [t for t in all_tasks if t['id'] not in already]


def get_unassigned_for_task(plan_id, date_str, task_id, show_all=False):
    """Vrátí (primary, other_count) pro panel přiřazení zaměstnance.

    primary = zaměstnanci bez práce, jejichž plánované oddělení odpovídá
              kategorii (work_plan) dané práce, nebo nemají oddělení v plánu.
    other   = ostatní (jiná kategorie), zobrazí se jen při show_all=True.
    Filtruje: na nástěnce přiřazeni, celodenně absenti, nemají ten den práci.
    """
    db = get_db()

    # Kategorie (work_plan) oddělení, ke které práce patří
    task_info = db.execute(
        """SELECT COALESCE(d.work_plan, 1) as work_plan
           FROM tasks t LEFT JOIN departments d ON d.id = t.department_id
           WHERE t.id = ?""",
        (task_id,)
    ).fetchone()
    task_work_plan = task_info['work_plan'] if task_info else 1

    # Zaměstnanci přiřazeni k JAKÉKOLI práci na nástěnce dnes
    on_board = {r[0] for r in db.execute(
        """SELECT DISTINCT a.employee_id FROM board_task_assignments bta
           JOIN assignments a ON a.id = bta.assignment_id
           WHERE a.plan_id=? AND a.date=?""",
        (plan_id, date_str)
    ).fetchall()}

    # Celodenní absence
    absent = {r[0] for r in db.execute(
        """SELECT DISTINCT employee_id FROM constraints
           WHERE date_from <= ? AND date_to >= ?
             AND (half_day IS NULL OR half_day = 0)""",
        (date_str, date_str)
    ).fetchall()}

    # Plánované oddělení zaměstnance pro tento den (z assignments)
    dept_rows = db.execute(
        """SELECT a.employee_id, a.department_id,
                  COALESCE(d.work_plan, 1) as work_plan
           FROM assignments a
           LEFT JOIN departments d ON d.id = a.department_id
           WHERE a.plan_id=? AND a.date=? AND a.is_absence=0""",
        (plan_id, date_str)
    ).fetchall()
    emp_plan_dept = {
        r['employee_id']: {'dept_id': r['department_id'], 'work_plan': r['work_plan']}
        for r in dept_rows
    }

    from app.models.employee import get_all_employees, employee_works_on_day
    from datetime import date as _date
    parts = date_str.split('-')
    weekday = _date(int(parts[0]), int(parts[1]), int(parts[2])).weekday()

    primary, other = [], []
    for e in get_all_employees(active_only=True):
        if e['id'] in on_board or e['id'] in absent or not employee_works_on_day(e, weekday):
            continue
        emp_data = {'id': e['id'], 'name': e['name'], 'color': _emp_color(e['id'])}
        info = emp_plan_dept.get(e['id'])
        if info and info['dept_id']:
            # Má předvyplněné oddělení — zařaď podle shody work_plan
            if info['work_plan'] == task_work_plan:
                primary.append(emp_data)
            else:
                other.append(emp_data)
        else:
            # Bez přiřazeného oddělení → nabídnout vždy primárně
            primary.append(emp_data)

    if show_all:
        return primary + other, 0
    return primary, len(other)


def board_set_note(assignment_id, note):
    """Uloží poznámku k přiřazení zaměstnance (platí pro celý den)."""
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
