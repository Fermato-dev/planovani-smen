from flask import Blueprint, render_template, request, redirect, url_for, flash
from app.models.constraint import (
    get_all_constraints, get_constraint, create_constraint,
    update_constraint, delete_constraint
)
from app.models.employee import get_all_employees
from app.models.company_vacation import (
    get_all_company_vacations, create_company_vacation,
    delete_company_vacation, update_company_vacation
)
from app.services.planner_service import ABSENCE_TYPES

bp = Blueprint('constraints', __name__, url_prefix='/constraints')


@bp.route('/')
def index():
    employee_id = request.args.get('employee_id', type=int)
    tab = request.args.get('tab', 'absence')
    constraints = get_all_constraints(employee_id=employee_id)
    employees = get_all_employees(active_only=True)
    company_vacations = get_all_company_vacations()
    return render_template('constraints/index.html',
                           constraints=constraints,
                           employees=employees,
                           absence_types=ABSENCE_TYPES,
                           selected_employee=employee_id,
                           company_vacations=company_vacations,
                           active_tab=tab)


@bp.route('/company-vacation/add', methods=['POST'])
def add_company_vacation():
    name = request.form.get('name', '').strip()
    date_from = request.form.get('date_from', '').strip()
    date_to = request.form.get('date_to', '').strip()
    if not name or not date_from or not date_to:
        flash('Vyplňte všechny údaje.', 'error')
        return redirect(url_for('constraints.index', tab='celozavodni'))
    if date_to < date_from:
        flash('Datum "do" nesmí být před datem "od".', 'error')
        return redirect(url_for('constraints.index', tab='celozavodni'))
    create_company_vacation(name, date_from, date_to)
    flash('Celozávodní dovolená přidána.', 'success')
    return redirect(url_for('constraints.index', tab='celozavodni'))


@bp.route('/company-vacation/<int:vac_id>/edit', methods=['POST'])
def edit_company_vacation(vac_id):
    name = request.form.get('name', '').strip()
    date_from = request.form.get('date_from', '').strip()
    date_to = request.form.get('date_to', '').strip()
    if date_to < date_from:
        flash('Datum "do" nesmí být před datem "od".', 'error')
        return redirect(url_for('constraints.index', tab='celozavodni'))
    update_company_vacation(vac_id, name, date_from, date_to)
    flash('Celozávodní dovolená aktualizována.', 'success')
    return redirect(url_for('constraints.index', tab='celozavodni'))


@bp.route('/company-vacation/<int:vac_id>/delete', methods=['POST'])
def delete_company_vacation_route(vac_id):
    delete_company_vacation(vac_id)
    flash('Celozávodní dovolená smazána.', 'success')
    return redirect(url_for('constraints.index', tab='celozavodni'))


@bp.route('/add', methods=['POST'])
def add():
    employee_id = request.form.get('employee_id', type=int)
    date_from = request.form.get('date_from', '').strip()
    date_to = request.form.get('date_to', '').strip()
    type_ = request.form.get('type', '').strip()
    note = request.form.get('note', '').strip()

    if not employee_id or not date_from or not date_to or not type_:
        flash('Vyplňte všechny povinné údaje.', 'error')
        return redirect(url_for('constraints.index'))

    if date_to < date_from:
        flash('Datum "do" nesmí být před datem "od".', 'error')
        return redirect(url_for('constraints.index'))

    try:
        create_constraint(employee_id, date_from, date_to, type_, note=note)
        flash('Omezení přidáno.', 'success')
    except Exception as e:
        flash(f'Chyba: {e}', 'error')

    return redirect(url_for('constraints.index'))


@bp.route('/<int:constraint_id>/edit', methods=['POST'])
def edit(constraint_id):
    employee_id = request.form.get('employee_id', type=int)
    date_from = request.form.get('date_from', '').strip()
    date_to = request.form.get('date_to', '').strip()
    type_ = request.form.get('type', '').strip()
    note = request.form.get('note', '').strip()

    if date_to < date_from:
        flash('Datum "do" nesmí být před datem "od".', 'error')
        return redirect(url_for('constraints.index'))

    update_constraint(constraint_id,
                      employee_id=employee_id,
                      date_from=date_from,
                      date_to=date_to,
                      type=type_,
                      note=note)
    flash('Omezení aktualizováno.', 'success')
    return redirect(url_for('constraints.index'))


@bp.route('/<int:constraint_id>/delete', methods=['POST'])
def delete(constraint_id):
    try:
        delete_constraint(constraint_id)
        flash('Omezení smazáno.', 'success')
    except Exception as e:
        flash(f'Chyba: {e}', 'error')
    return redirect(url_for('constraints.index'))
