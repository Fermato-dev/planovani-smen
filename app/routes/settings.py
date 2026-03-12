import smtplib
import logging
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify

logger = logging.getLogger(__name__)
from app.models.department import (
    get_all_departments, get_department, create_department, update_department, delete_department,
    get_tasks_for_department, get_all_tasks, create_task, update_task, get_task
)
from app.models.shift import get_all_shifts, get_shift, create_shift, update_shift, delete_shift
from app.models.app_settings import get_smtp_settings, save_smtp_settings

bp = Blueprint('settings', __name__, url_prefix='/settings')


@bp.route('/')
def index():
    active_tab = request.args.get('tab', '')
    departments = get_all_departments(active_only=False)
    shifts = get_all_shifts()
    tasks = get_all_tasks(active_only=False)
    smtp = get_smtp_settings()
    return render_template('settings/index.html',
                           departments=departments, shifts=shifts, tasks=tasks,
                           smtp=smtp, active_tab=active_tab)


# --- Departments ---

@bp.route('/department/add', methods=['POST'])
def department_add():
    name = request.form.get('name', '').strip()
    full_name = request.form.get('full_name', '').strip()
    color = request.form.get('color', 'D9D9D9').strip().lstrip('#')
    min_staff = int(request.form.get('min_staff', 0))
    max_staff = int(request.form.get('max_staff', 99))
    if not name:
        flash('Zadejte zkratku oddělení.', 'error')
        return redirect(url_for('settings.index'))
    try:
        create_department(name, full_name, color, min_staff, max_staff)
        flash(f'Oddělení {name} přidáno.', 'success')
    except Exception as e:
        flash(f'Chyba: {e}', 'error')
    return redirect(url_for('settings.index'))


@bp.route('/department/<int:dept_id>/edit', methods=['POST'])
def department_edit(dept_id):
    update_department(dept_id,
                      name=request.form.get('name', '').strip(),
                      full_name=request.form.get('full_name', '').strip(),
                      color=request.form.get('color', 'D9D9D9').strip().lstrip('#'),
                      min_staff=int(request.form.get('min_staff', 0)),
                      max_staff=int(request.form.get('max_staff', 99)))
    flash('Oddělení aktualizováno.', 'success')
    return redirect(url_for('settings.index'))


@bp.route('/department/<int:dept_id>/toggle', methods=['POST'])
def department_toggle(dept_id):
    dept = get_department(dept_id)
    if dept:
        update_department(dept_id, active=0 if dept['active'] else 1)
        status = 'deaktivováno' if dept['active'] else 'aktivováno'
        flash(f'Oddělení {dept["name"]} {status}.', 'success')
    return redirect(url_for('settings.index'))


# --- Tasks ---

@bp.route('/task/add', methods=['POST'])
def task_add():
    department_id = int(request.form.get('department_id', 0))
    name = request.form.get('name', '').strip()
    min_staff = int(request.form.get('min_staff', 0))
    max_staff = int(request.form.get('max_staff', 99))
    if not name or not department_id:
        flash('Zadejte název práce a oddělení.', 'error')
        return redirect(url_for('settings.index'))
    try:
        create_task(department_id, name, min_staff, max_staff)
        flash(f'Práce "{name}" přidána.', 'success')
    except Exception as e:
        flash(f'Chyba: {e}', 'error')
    return redirect(url_for('settings.index'))


@bp.route('/task/<int:task_id>/edit', methods=['POST'])
def task_edit(task_id):
    name = request.form.get('name', '').strip()
    department_id = int(request.form.get('department_id', 0))
    min_staff = int(request.form.get('min_staff', 0))
    max_staff = int(request.form.get('max_staff', 99))
    update_task(task_id, name=name, department_id=department_id,
                min_staff=min_staff, max_staff=max_staff)
    flash(f'Práce "{name}" aktualizována.', 'success')
    return redirect(url_for('settings.index'))


@bp.route('/task/<int:task_id>/toggle', methods=['POST'])
def task_toggle(task_id):
    t = get_task(task_id)
    if t:
        update_task(task_id, active=0 if t['active'] else 1)
        flash(f'Práce "{t["name"]}" {"deaktivována" if t["active"] else "aktivována"}.', 'success')
    return redirect(url_for('settings.index'))


# --- Shifts ---

@bp.route('/shift/add', methods=['POST'])
def shift_add():
    name = request.form.get('name', '').strip()
    start_time = request.form.get('start_time', '').strip()
    end_time = request.form.get('end_time', '').strip()
    is_default = 1 if request.form.get('is_default') else 0
    if not name or not start_time or not end_time:
        flash('Vyplňte všechny údaje směny.', 'error')
        return redirect(url_for('settings.index'))
    try:
        create_shift(name, start_time, end_time, is_default)
        flash(f'Směna "{name}" přidána.', 'success')
    except Exception as e:
        flash(f'Chyba: {e}', 'error')
    return redirect(url_for('settings.index'))


@bp.route('/shift/<int:shift_id>/edit', methods=['POST'])
def shift_edit(shift_id):
    update_shift(shift_id,
                 name=request.form.get('name', '').strip(),
                 start_time=request.form.get('start_time', '').strip(),
                 end_time=request.form.get('end_time', '').strip(),
                 is_default=1 if request.form.get('is_default') else 0)
    flash('Směna aktualizována.', 'success')
    return redirect(url_for('settings.index'))


@bp.route('/shift/<int:shift_id>/delete', methods=['POST'])
def shift_delete(shift_id):
    try:
        delete_shift(shift_id)
        flash('Směna smazána.', 'success')
    except Exception as e:
        flash(f'Chyba: {e}', 'error')
    return redirect(url_for('settings.index'))


# --- SMTP / Email ---

@bp.route('/smtp', methods=['POST'])
def smtp_save():
    """Save SMTP settings and optionally send test email."""
    server = request.form.get('smtp_server', '').strip()
    port = request.form.get('smtp_port', '587').strip()
    use_tls = request.form.get('smtp_use_tls', 'true')
    username = request.form.get('smtp_username', '').strip()
    password = request.form.get('smtp_password', '').strip()
    sender = request.form.get('smtp_sender', '').strip()

    save_smtp_settings(server, int(port) if port else 587, use_tls, username, password, sender)
    flash('SMTP nastavení uloženo.', 'success')

    # Test connection if requested
    action = request.form.get('action', '')
    if action == 'test':
        smtp = get_smtp_settings()
        test_user = smtp['username']
        test_pass = smtp['password']
        if not test_user or not test_pass:
            flash('Pro test je potřeba vyplnit uživatele a heslo.', 'error')
        else:
            srv = None
            try:
                port = int(smtp['port'])
                use_tls = smtp['use_tls']
                logger.info(f"SMTP test: server={smtp['server']}, port={port}, use_tls={use_tls}, user={test_user}")

                if port == 465 or use_tls == 'ssl':
                    logger.info("Using SMTP_SSL")
                    srv = smtplib.SMTP_SSL(smtp['server'], port, timeout=15)
                else:
                    logger.info("Using SMTP plain connect")
                    srv = smtplib.SMTP(smtp['server'], port, timeout=15)

                srv.set_debuglevel(1)
                resp = srv.ehlo()
                logger.info(f"EHLO response: {resp}")

                if port != 465 and use_tls != 'false' and use_tls != 'ssl':
                    logger.info("Starting STARTTLS")
                    srv.starttls()
                    resp2 = srv.ehlo()
                    logger.info(f"EHLO after STARTTLS: {resp2}")

                logger.info("Attempting login...")
                srv.login(test_user, test_pass)
                logger.info("Login successful!")
                flash(f'Připojení k {smtp["server"]}:{port} úspěšné! ✓', 'success')
            except smtplib.SMTPAuthenticationError as e:
                logger.error(f"SMTP auth error: {e}")
                flash('Chyba autentizace — zkontrolujte uživatele a heslo (u Gmailu použijte App Password).', 'error')
            except Exception as e:
                logger.error(f"SMTP error: {type(e).__name__}: {e}", exc_info=True)
                flash(f'Připojení selhalo: {type(e).__name__}: {e}', 'error')
            finally:
                if srv:
                    try:
                        srv.quit()
                    except Exception:
                        pass

    return redirect(url_for('settings.index', tab='email'))
