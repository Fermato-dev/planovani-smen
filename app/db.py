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
        _migrate_db(g.db)
    return g.db


def _migrate_db(db):
    """Run lightweight migrations for schema changes."""
    cols = [r[1] for r in db.execute("PRAGMA table_info(employees)").fetchall()]
    if cols and 'email' not in cols:
        db.execute("ALTER TABLE employees ADD COLUMN email TEXT DEFAULT ''")
        db.commit()

    # Ensure app_settings table exists
    db.execute("""
        CREATE TABLE IF NOT EXISTS app_settings (
            key TEXT PRIMARY KEY,
            value TEXT DEFAULT ''
        )
    """)
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
