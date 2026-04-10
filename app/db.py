import sqlite3
import click
from flask import g, current_app


def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(
            current_app.config['DATABASE'],
            detect_types=sqlite3.PARSE_DECLTYPES
        )
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
        g.db.execute("PRAGMA journal_mode = WAL")
        _ensure_schema(g.db)
        _migrate_db(g.db)
    return g.db


def _ensure_schema(db):
    """Create tables if they don't exist yet (fresh install)."""
    import os
    from flask import current_app
    schema_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'app', 'schema.sql')
    if not os.path.exists(schema_path):
        # Try relative to app root
        schema_path = os.path.join(current_app.root_path, 'schema.sql')
    if os.path.exists(schema_path):
        with open(schema_path, 'r', encoding='utf-8') as f:
            db.executescript(f.read())


def _migrate_db(db):
    """Run lightweight migrations for schema changes."""
    # Only migrate if employees table exists
    tables = [r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]

    if 'employees' in tables:
        cols = [r[1] for r in db.execute("PRAGMA table_info(employees)").fetchall()]
        if 'email' not in cols:
            db.execute("ALTER TABLE employees ADD COLUMN email TEXT DEFAULT ''")
            db.commit()

    # Ensure app_settings table exists FIRST (needed by subsequent migrations)
    db.execute("""
        CREATE TABLE IF NOT EXISTS app_settings (
            key TEXT PRIMARY KEY,
            value TEXT DEFAULT ''
        )
    """)
    db.commit()

    # Přidat příznak work_plan k oddělením (filtr pro plán práce)
    if 'departments' in tables:
        dept_cols = [r[1] for r in db.execute("PRAGMA table_info(departments)").fetchall()]
        if 'work_plan' not in dept_cols:
            db.execute("ALTER TABLE departments ADD COLUMN work_plan INTEGER DEFAULT 1")
            db.commit()

    # Jednorázová migrace: nastavit work_plan=0 pro expedici/sklad (pokud ještě neproběhla)
    wp_init = db.execute("SELECT value FROM app_settings WHERE key = 'wp_defaults_applied'").fetchone()
    if not wp_init:
        db.execute(
            "UPDATE departments SET work_plan = 0 WHERE name IN ('EXP', 'SKL', 'SKLAD', 'Sklad', 'Expedice', 'Sklady')"
        )
        db.execute("INSERT OR REPLACE INTO app_settings (key, value) VALUES ('wp_defaults_applied', '1')")
        db.commit()

    # Add email tracking to weekly_plans (two-phase: first send + update send)
    if 'weekly_plans' in tables:
        plan_cols = [r[1] for r in db.execute("PRAGMA table_info(weekly_plans)").fetchall()]
        if 'email_sent_at' not in plan_cols:
            db.execute("ALTER TABLE weekly_plans ADD COLUMN email_sent_at TIMESTAMP")
            db.execute("ALTER TABLE weekly_plans ADD COLUMN email_sent_count INTEGER DEFAULT 0")
            db.commit()
        if 'email_first_sent_at' not in plan_cols:
            db.execute("ALTER TABLE weekly_plans ADD COLUMN email_first_sent_at TIMESTAMP")
            db.execute("ALTER TABLE weekly_plans ADD COLUMN email_first_sent_to INTEGER DEFAULT 0")
            db.execute("ALTER TABLE weekly_plans ADD COLUMN email_update_sent_at TIMESTAMP")
            db.execute("ALTER TABLE weekly_plans ADD COLUMN email_update_sent_to INTEGER DEFAULT 0")
            # Migrate existing data from legacy columns
            db.execute("""UPDATE weekly_plans
                          SET email_first_sent_at = email_sent_at,
                              email_first_sent_to = email_sent_count
                          WHERE email_sent_at IS NOT NULL""")
            db.commit()

    # Ensure users table exists
    db.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            display_name TEXT NOT NULL DEFAULT '',
            active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_login TIMESTAMP
        )
    """)
    db.commit()

    # Ensure task_date_requirements table exists
    db.execute("""
        CREATE TABLE IF NOT EXISTS task_date_requirements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id INTEGER NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
            date_from DATE NOT NULL,
            date_to DATE,
            min_staff INTEGER NOT NULL DEFAULT 0,
            note TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    db.commit()

    # Plán práce (denní výrobní plán – lahvování a příprava)
    db.execute("""
        CREATE TABLE IF NOT EXISTS work_plan_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            plan_id INTEGER NOT NULL REFERENCES weekly_plans(id) ON DELETE CASCADE,
            date DATE NOT NULL,
            section TEXT NOT NULL DEFAULT '',
            sort_order INTEGER NOT NULL DEFAULT 0,
            time_from TEXT NOT NULL DEFAULT '',
            time_to TEXT NOT NULL DEFAULT '',
            line TEXT NOT NULL DEFAULT '',
            product TEXT NOT NULL DEFAULT '',
            quantity TEXT NOT NULL DEFAULT '',
            note TEXT NOT NULL DEFAULT ''
        )
    """)
    db.commit()

    # Denní potřeby obsazení (nová tabulka pro plánování)
    db.execute("""
        CREATE TABLE IF NOT EXISTS day_requirements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            plan_id INTEGER NOT NULL REFERENCES weekly_plans(id) ON DELETE CASCADE,
            date DATE NOT NULL,
            task_id INTEGER NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
            min_count INTEGER NOT NULL DEFAULT 0,
            max_count INTEGER DEFAULT NULL,
            UNIQUE(plan_id, date, task_id)
        )
    """)
    db.commit()

    # Auto-create default admin if no users exist
    user_count = db.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    if user_count == 0:
        from werkzeug.security import generate_password_hash
        import os
        default_pw = os.environ.get('ADMIN_PASSWORD', 'fermato2026')
        db.execute(
            "INSERT INTO users (username, password_hash, display_name) VALUES (?, ?, ?)",
            ('admin', generate_password_hash(default_pw), 'Administrátor')
        )
        db.commit()


def close_db(e=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()


def init_db():
    """Initialize database from schema.sql."""
    db = get_db()
    with current_app.open_resource('schema.sql') as f:
        db.executescript(f.read().decode('utf8'))


def init_app(app):
    """Register database functions with Flask app."""
    app.teardown_appcontext(close_db)

    @app.cli.command('init-db')
    def init_db_command():
        init_db()
        print('Database initialized.')

    @app.cli.command('create-user')
    @click.argument('username')
    @click.option('--display-name', '-n', default='', help='Zobrazované jméno')
    def create_user_command(username, display_name):
        """Vytvořit nový uživatelský účet."""
        import getpass
        from app.models.user import get_user_by_username, create_user

        if get_user_by_username(username):
            print(f'Chyba: Uživatel "{username}" již existuje.')
            return

        password = getpass.getpass('Heslo: ')
        confirm = getpass.getpass('Potvrzení hesla: ')

        if password != confirm:
            print('Chyba: Hesla se neshodují.')
            return

        if len(password) < 6:
            print('Chyba: Heslo musí mít alespoň 6 znaků.')
            return

        create_user(username, password, display_name or username)
        print(f'Uživatel "{username}" byl vytvořen.')
