-- =============================================
-- Plánování směn - Databázové schéma
-- =============================================

-- Úseky (departments)
CREATE TABLE IF NOT EXISTS departments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    full_name TEXT,
    color TEXT NOT NULL DEFAULT 'D9D9D9',
    min_staff INTEGER DEFAULT 0,
    max_staff INTEGER DEFAULT 99,
    sort_order INTEGER DEFAULT 0,
    active INTEGER DEFAULT 1
);

-- Práce (tasks) v rámci úseku
CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    department_id INTEGER NOT NULL REFERENCES departments(id),
    name TEXT NOT NULL,
    min_staff INTEGER DEFAULT 0,
    max_staff INTEGER DEFAULT 99,
    active INTEGER DEFAULT 1,
    UNIQUE(department_id, name)
);

-- Šablony směn
CREATE TABLE IF NOT EXISTS shift_templates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    start_time TEXT NOT NULL,
    end_time TEXT NOT NULL,
    is_default INTEGER DEFAULT 0
);

-- Zaměstnanci
CREATE TABLE IF NOT EXISTS employees (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    default_shift_id INTEGER REFERENCES shift_templates(id),
    active INTEGER DEFAULT 1,
    note TEXT DEFAULT '',
    email TEXT DEFAULT '',
    sort_order INTEGER DEFAULT 0
);

-- Kvalifikace zaměstnanců (které úseky/práce mohou dělat)
CREATE TABLE IF NOT EXISTS employee_qualifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_id INTEGER NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
    department_id INTEGER NOT NULL REFERENCES departments(id),
    task_id INTEGER REFERENCES tasks(id),
    UNIQUE(employee_id, department_id, task_id)
);

-- Výchozí týdenní vzor zaměstnance
CREATE TABLE IF NOT EXISTS employee_default_pattern (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_id INTEGER NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
    day_of_week INTEGER NOT NULL,
    shift_template_id INTEGER REFERENCES shift_templates(id),
    department_id INTEGER REFERENCES departments(id),
    task_id INTEGER REFERENCES tasks(id),
    UNIQUE(employee_id, day_of_week)
);

-- Týdenní plány
CREATE TABLE IF NOT EXISTS weekly_plans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    week_start DATE NOT NULL UNIQUE,
    week_number INTEGER NOT NULL,
    year INTEGER NOT NULL,
    status TEXT DEFAULT 'draft',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Přiřazení (zaměstnanec × den × směna × úsek × práce)
CREATE TABLE IF NOT EXISTS assignments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    plan_id INTEGER NOT NULL REFERENCES weekly_plans(id) ON DELETE CASCADE,
    employee_id INTEGER NOT NULL REFERENCES employees(id),
    date DATE NOT NULL,
    shift_template_id INTEGER REFERENCES shift_templates(id),
    department_id INTEGER REFERENCES departments(id),
    task_id INTEGER REFERENCES tasks(id),
    note TEXT DEFAULT '',
    is_absence INTEGER DEFAULT 0,
    absence_type TEXT DEFAULT '',
    UNIQUE(plan_id, employee_id, date)
);

-- Nastavení aplikace (key-value)
CREATE TABLE IF NOT EXISTS app_settings (
    key TEXT PRIMARY KEY,
    value TEXT DEFAULT ''
);

-- Omezení / výjimky
CREATE TABLE IF NOT EXISTS constraints (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_id INTEGER NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
    date_from DATE NOT NULL,
    date_to DATE NOT NULL,
    type TEXT NOT NULL,
    subtype TEXT DEFAULT '',
    note TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Požadavky na obsazení práce pro konkrétní datum / rozsah
CREATE TABLE IF NOT EXISTS task_date_requirements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id INTEGER NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    date_from DATE NOT NULL,
    date_to DATE,           -- NULL = platí od date_from dále
    min_staff INTEGER NOT NULL DEFAULT 0,
    note TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Uživatelé (přihlášení)
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    display_name TEXT NOT NULL DEFAULT '',
    active INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP
);

-- Výchozí seed data jsou spravována přes _migrate_db v db.py (jednorázový INSERT)
-- aby nedocházelo k obnovení smazaných záznamů při každém requestu.
