from datetime import datetime
from flask import Blueprint, render_template
from app.models.employee import get_all_employees
from app.models.department import get_all_departments
from app.models.shift import get_all_shifts

bp = Blueprint('dashboard', __name__)


@bp.route('/')
def index():
    employees = get_all_employees()
    departments = get_all_departments()
    shifts = get_all_shifts()
    return render_template('dashboard/index.html',
                           employees=employees,
                           departments=departments,
                           shifts=shifts,
                           now=datetime.today())
