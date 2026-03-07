import os
from datetime import date as date_type
from flask import Flask, request, redirect, url_for
from flask_login import LoginManager, current_user


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

    return app
