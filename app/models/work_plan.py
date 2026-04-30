"""Model pro denní plán práce (lahvování a příprava)."""
from app.db import get_db

# Výchozí šablona – Lahvování
DEFAULT_LAHVOVANI = [
    {'time_from': '06:00', 'time_to': '06:15', 'line': 'LAH 1', 'product': 'Příprava na lahvování', 'quantity': '', 'note': 'proplach lahvovačky, kompresor, lahvičky, etikety, lampa na folie, kartony, přečerpání'},
    {'time_from': '06:00', 'time_to': '06:15', 'line': 'LAH 2', 'product': 'Příprava na lahvování', 'quantity': '', 'note': 'proplach lahvovačky, kompresor, lahvičky, etikety, lampa na folie, kartony, přečerpání'},
    {'time_from': '06:15', 'time_to': '08:00', 'line': 'LAH 1', 'product': '', 'quantity': '', 'note': ''},
    {'time_from': '06:15', 'time_to': '08:00', 'line': 'LAH 2', 'product': '', 'quantity': '', 'note': ''},
    {'time_from': '08:00', 'time_to': '08:20', 'line': '',       'product': 'Porada / přestávka', 'quantity': '', 'note': ''},
    {'time_from': '08:20', 'time_to': '11:30', 'line': 'LAH 1', 'product': '', 'quantity': '', 'note': ''},
    {'time_from': '08:20', 'time_to': '11:30', 'line': 'LAH 2', 'product': '', 'quantity': '', 'note': ''},
    {'time_from': '11:30', 'time_to': '12:00', 'line': '',       'product': 'Oběd', 'quantity': '', 'note': ''},
    {'time_from': '12:00', 'time_to': '14:30', 'line': 'LAH 1', 'product': '', 'quantity': '', 'note': ''},
    {'time_from': '12:00', 'time_to': '14:30', 'line': 'LAH 2', 'product': '', 'quantity': '', 'note': ''},
]

# Výchozí šablona – Příprava
DEFAULT_PRIPRAVA = [
    {'time_from': '06:00', 'time_to': '08:00', 'line': '', 'product': '', 'quantity': '', 'note': ''},
    {'time_from': '08:00', 'time_to': '08:20', 'line': '', 'product': 'Porada / přestávka', 'quantity': '', 'note': ''},
    {'time_from': '08:20', 'time_to': '11:30', 'line': '', 'product': '', 'quantity': '', 'note': ''},
    {'time_from': '11:30', 'time_to': '12:00', 'line': '', 'product': 'Oběd', 'quantity': '', 'note': ''},
    {'time_from': '12:00', 'time_to': '14:30', 'line': '', 'product': '', 'quantity': '', 'note': ''},
]

# Výchozí šablona – Koření
DEFAULT_KORENI = [
    {'time_from': '06:00', 'time_to': '08:00', 'line': '', 'product': '', 'quantity': '', 'note': ''},
    {'time_from': '08:00', 'time_to': '08:20', 'line': '', 'product': 'Porada / přestávka', 'quantity': '', 'note': ''},
    {'time_from': '08:20', 'time_to': '11:30', 'line': '', 'product': '', 'quantity': '', 'note': ''},
    {'time_from': '11:30', 'time_to': '12:00', 'line': '', 'product': 'Oběd', 'quantity': '', 'note': ''},
    {'time_from': '12:00', 'time_to': '14:30', 'line': '', 'product': '', 'quantity': '', 'note': ''},
]


def get_entries(plan_id, date, section):
    """Vrátí všechny záznamy pro daný den a sekci, seřazené podle sort_order."""
    db = get_db()
    rows = db.execute(
        """SELECT * FROM work_plan_entries
           WHERE plan_id = ? AND date = ? AND section = ?
           ORDER BY time_from, line, sort_order""",
        (plan_id, date, section)
    ).fetchall()
    return [dict(r) for r in rows]


def save_entries(plan_id, date, section, entries):
    """Uloží záznamy pro daný den a sekci (smaže staré, vloží nové)."""
    db = get_db()
    db.execute(
        "DELETE FROM work_plan_entries WHERE plan_id = ? AND date = ? AND section = ?",
        (plan_id, date, section)
    )
    for i, e in enumerate(entries):
        # Přeskočíme zcela prázdné řádky
        if not any([e.get('time_from'), e.get('time_to'), e.get('line'),
                    e.get('product'), e.get('quantity'), e.get('note')]):
            continue
        db.execute(
            """INSERT INTO work_plan_entries
               (plan_id, date, section, sort_order, time_from, time_to, line, product, quantity, note)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (plan_id, date, section, i,
             e.get('time_from', ''), e.get('time_to', ''),
             e.get('line', ''), e.get('product', ''),
             e.get('quantity', ''), e.get('note', ''))
        )
    db.commit()


def get_default_entries(section):
    """Vrátí výchozí šablonu pro danou sekci."""
    if section == 'lahvovani':
        return [dict(e) for e in DEFAULT_LAHVOVANI]
    elif section == 'priprava':
        return [dict(e) for e in DEFAULT_PRIPRAVA]
    elif section == 'koreni':
        return [dict(e) for e in DEFAULT_KORENI]
    return []


def get_entries_or_default(plan_id, date, section):
    """Vrátí záznamy pro den – pokud žádné nejsou, vrátí výchozí šablonu."""
    entries = get_entries(plan_id, date, section)
    if entries:
        return entries, False  # False = načteno z DB
    return get_default_entries(section), True  # True = je to šablona


def copy_from_previous_day(plan_id, date, section):
    """Zkopíruje záznamy z nejbližšího předchozího dne se záznamy. Vrátí seznam záznamů (neuloží)."""
    from datetime import date as date_type, timedelta
    db = get_db()
    # Hledáme předchozí den s daty (max 30 dní zpátky)
    parts = date.split('-')
    d = date_type(int(parts[0]), int(parts[1]), int(parts[2]))
    for i in range(1, 31):
        prev_date = (d - timedelta(days=i)).isoformat()
        rows = db.execute(
            """SELECT * FROM work_plan_entries
               WHERE plan_id = ? AND date = ? AND section = ?
               ORDER BY time_from, line, sort_order""",
            (plan_id, prev_date, section)
        ).fetchall()
        if rows:
            return [dict(r) for r in rows], prev_date
    return get_default_entries(section), None


def get_employees_for_day(plan_id, date):
    """Vrátí zaměstnance přiřazené na daný den, seskupené podle práce.
    Zahrnuje pouze oddělení s work_plan = 1."""
    db = get_db()
    rows = db.execute(
        """SELECT e.name,
                  COALESCE(t.name, d.name) as group_label,
                  d.color as dept_color,
                  t.name as task_name,
                  d.sort_order as dept_order
           FROM assignments a
           JOIN employees e ON a.employee_id = e.id
           LEFT JOIN departments d ON a.department_id = d.id
           LEFT JOIN tasks t ON a.task_id = t.id
           WHERE a.plan_id = ? AND a.date = ? AND a.is_absence = 0
             AND a.department_id IS NOT NULL
             AND COALESCE(d.work_plan, 1) = 1
           ORDER BY d.sort_order, COALESCE(t.name, d.name), e.name""",
        (plan_id, date)
    ).fetchall()
    from collections import OrderedDict
    result = OrderedDict()
    for r in rows:
        label = r['group_label'] or '—'
        color = r['dept_color'] or 'D9D9D9'
        if label not in result:
            result[label] = {'color': color, 'employees': []}
        result[label]['employees'].append(r['name'])
    return result


def has_entries_map(plan_id, dates):
    """Vrátí slovník {date_str: {'lahvovani': bool, 'priprava': bool}} pro seznam datumů."""
    db = get_db()
    date_strs = [d.isoformat() for d in dates]
    rows = db.execute(
        f"""SELECT date, section FROM work_plan_entries
            WHERE plan_id = ? AND date IN ({','.join('?' * len(date_strs))})
            GROUP BY date, section""",
        [plan_id] + date_strs
    ).fetchall()
    result = {d: {'lahvovani': False, 'priprava': False} for d in date_strs}
    for r in rows:
        ds = r['date']
        if ds in result:
            result[ds][r['section']] = True
    return result
