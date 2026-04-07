import os
import shutil
import logging
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, send_file, current_app

logger = logging.getLogger(__name__)
from app.models.department import (
    get_all_departments, get_department, create_department, update_department, delete_department,
    get_tasks_for_department, get_all_tasks, create_task, update_task, get_task, delete_task
)
from app.models.shift import get_all_shifts, get_shift, create_shift, update_shift, delete_shift
from app.models.app_settings import get_smtp_settings, save_smtp_settings, get_setting, set_setting
from app.models.task_requirement import (
    get_all_requirements, get_requirement, create_requirement, update_requirement, delete_requirement
)

bp = Blueprint('settings', __name__, url_prefix='/settings')


@bp.route('/')
def index():
    active_tab = request.args.get('tab', '')
    departments = get_all_departments(active_only=False)
    shifts = get_all_shifts()
    tasks = get_all_tasks(active_only=False)
    smtp = get_smtp_settings()
    resend_key = get_setting('resend_api_key', '') or os.environ.get('RESEND_API_KEY', '')
    requirements = get_all_requirements()
    return render_template('settings/index.html',
                           departments=departments, shifts=shifts, tasks=tasks,
                           smtp=smtp, resend_key=resend_key, requirements=requirements,
                           active_tab=active_tab)


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
                      max_staff=int(request.form.get('max_staff', 99)),
                      work_plan=1 if request.form.get('work_plan') else 0)
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


@bp.route('/task/<int:task_id>/delete', methods=['POST'])
def task_delete(task_id):
    try:
        t = get_task(task_id)
        delete_task(task_id)
        flash(f'Práce "{t["name"]}" smazána.', 'success') if t else None
    except Exception as e:
        logger.error(f"Task delete error: {e}", exc_info=True)
        flash(f'Chyba při mazání práce: {e}', 'error')
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
        s = get_shift(shift_id)
        delete_shift(shift_id)
        flash(f'Směna "{s["name"]}" smazána.', 'success') if s else None
    except Exception as e:
        logger.error(f"Shift delete error: {e}", exc_info=True)
        flash(f'Chyba při mazání směny: {e}', 'error')
    return redirect(url_for('settings.index'))


# --- Task Date Requirements ---

@bp.route('/requirement/add', methods=['POST'])
def requirement_add():
    task_id = int(request.form.get('task_id', 0))
    date_from = request.form.get('date_from', '').strip()
    date_to = request.form.get('date_to', '').strip() or None
    min_staff = int(request.form.get('min_staff', 0))
    note = request.form.get('note', '').strip()
    if not task_id or not date_from:
        flash('Vyberte práci a zadejte datum od.', 'error')
        return redirect(url_for('settings.index', tab='requirements'))
    try:
        create_requirement(task_id, date_from, date_to, min_staff, note)
        flash('Požadavek přidán.', 'success')
    except Exception as e:
        flash(f'Chyba: {e}', 'error')
    return redirect(url_for('settings.index', tab='requirements'))


@bp.route('/requirement/<int:req_id>/edit', methods=['POST'])
def requirement_edit(req_id):
    task_id = int(request.form.get('task_id', 0))
    date_from = request.form.get('date_from', '').strip()
    date_to = request.form.get('date_to', '').strip() or None
    min_staff = int(request.form.get('min_staff', 0))
    note = request.form.get('note', '').strip()
    update_requirement(req_id, task_id, date_from, date_to, min_staff, note)
    flash('Požadavek aktualizován.', 'success')
    return redirect(url_for('settings.index', tab='requirements'))


@bp.route('/requirement/<int:req_id>/delete', methods=['POST'])
def requirement_delete(req_id):
    delete_requirement(req_id)
    flash('Požadavek smazán.', 'success')
    return redirect(url_for('settings.index', tab='requirements'))


# --- Email (Resend API) ---

@bp.route('/email-save', methods=['POST'])
def email_save():
    """Save Resend email settings and optionally send test."""
    api_key = request.form.get('resend_api_key', '').strip()
    sender = request.form.get('email_sender', '').strip()

    if api_key:
        set_setting('resend_api_key', api_key)
    if sender:
        # Store sender in smtp_sender for backward compatibility
        save_smtp_settings('', 587, 'true', '', '', sender)

    flash('Nastavení emailu uloženo.', 'success')

    action = request.form.get('action', '')
    if action == 'test':
        try:
            from app.services.email_service import test_connection
            result = test_connection()
            flash(f'Testovací email odeslán! ✓ (ID: {result.get("id", "ok")})', 'success')
        except Exception as e:
            flash(f'Test selhal: {e}', 'error')

    return redirect(url_for('settings.index', tab='email'))


@bp.route('/backup/download')
def backup_download():
    """Stáhne databázový soubor jako zálohu."""
    db_path = current_app.config['DATABASE']
    if not os.path.exists(db_path):
        flash('Databáze nenalezena.', 'error')
        return redirect(url_for('settings.index'))
    return send_file(db_path, as_attachment=True,
                     download_name='planovani_smen_backup.db',
                     mimetype='application/octet-stream')


@bp.route('/backup/restore', methods=['POST'])
def backup_restore():
    """Obnoví databázi z nahraného souboru."""
    f = request.files.get('db_file')
    if not f or not f.filename.endswith('.db'):
        flash('Prosím nahraj soubor s příponou .db', 'error')
        return redirect(url_for('settings.index', tab='backup'))
    db_path = current_app.config['DATABASE']
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    # Záloha stávající DB
    if os.path.exists(db_path):
        shutil.copy2(db_path, db_path + '.before_restore')
    f.save(db_path)
    flash('Databáze obnovena. Restartuj aplikaci pro jistotu (nebo počkej pár sekund).', 'success')
    return redirect(url_for('settings.index', tab='backup'))
