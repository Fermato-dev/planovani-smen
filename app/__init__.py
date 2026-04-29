import os
from datetime import date as date_type
from flask import Flask, request, redirect, url_for
from flask_login import LoginManager, current_user


def _backup_database(db_path):
    """Create a rolling backup of the database on app startup (max 3 backups)."""
    import shutil
    from datetime import datetime
    if not os.path.exists(db_path):
        return
    backup_dir = os.path.join(os.path.dirname(db_path), 'backups')
    os.makedirs(backup_dir, exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_path = os.path.join(backup_dir, f'planovani_smen_{timestamp}.db')
    try:
        shutil.copy2(db_path, backup_path)
    except Exception:
        return  # silently skip if backup fails
    # Keep only last 3 backups
    backups = sorted(
        [f for f in os.listdir(backup_dir) if f.endswith('.db')],
        reverse=True
    )
    for old in backups[3:]:
        try:
            os.remove(os.path.join(backup_dir, old))
        except Exception:
            pass


def create_app():
    app = Flask(__name__, instance_relative_config=False)

    # Load config
    from config import Config
    app.config.from_object(Config)

    # Custom Jinja2 filters
    @app.template_filter('czdate')
    def czdate_filter(value):
        """Format date as Czech format: 09.03.2026"""
        if value is None:
            return ''
        if isinstance(value, str):
            parts = value.split('-')
            if len(parts) == 3:
                return f'{parts[2]}.{parts[1]}.{parts[0]}'
            return value
        if isinstance(value, date_type):
            return value.strftime('%d.%m.%Y')
        return str(value)

    # Ensure instance directories exist
    for d in [app.config['DATABASE'], app.config.get('EXPORT_DIR', ''), app.config.get('UPLOAD_DIR', '')]:
        dir_path = os.path.dirname(d) if d.endswith('.db') else d
        if dir_path:
            os.makedirs(dir_path, exist_ok=True)

    # Auto-backup database before anything else
    _backup_database(app.config['DATABASE'])

    # Initialize database
    from app.db import init_app, init_db
    init_app(app)

    # Auto-initialize DB on first run (no flask init-db needed)
    db_path = app.config['DATABASE']
    if not os.path.exists(db_path):
        with app.app_context():
            init_db()

    # Flask-Login setup
    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Pro přístup se prosím přihlaste.'
    login_manager.login_message_category = 'error'

    @login_manager.user_loader
    def load_user(user_id):
        from app.models.user import get_user_by_id
        return get_user_by_id(int(user_id))

    # Global auth - redirect unauthenticated to login
    @app.before_request
    def require_login():
        if request.endpoint and (
            request.endpoint.startswith('auth.') or
            request.endpoint == 'static'
        ):
            return
        if not current_user.is_authenticated:
            if request.headers.get('HX-Request'):
                return '', 401
            return redirect(url_for('auth.login', next=request.path))

    # Register auth blueprint first
    from app.routes.auth import bp as auth_bp
    app.register_blueprint(auth_bp)

    # Register blueprints
    from app.routes.dashboard import bp as dashboard_bp
    app.register_blueprint(dashboard_bp)

    from app.routes.employees import bp as employees_bp
    app.register_blueprint(employees_bp)

    from app.routes.constraints import bp as constraints_bp
    app.register_blueprint(constraints_bp)

    from app.routes.settings import bp as settings_bp
    app.register_blueprint(settings_bp)

    from app.routes.export import bp as export_bp
    app.register_blueprint(export_bp)

    from app.routes.import_csv import bp as import_bp
    app.register_blueprint(import_bp)

    from app.routes.planner import bp as planner_bp
    app.register_blueprint(planner_bp)

    from app.routes.work_plan import bp as work_plan_bp
    app.register_blueprint(work_plan_bp)

    from app.routes.capacity import bp as capacity_bp
    app.register_blueprint(capacity_bp)

    return app
