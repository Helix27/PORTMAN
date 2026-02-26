from flask import Blueprint

MODULE_INFO = {
    'code': 'FSAP01',
    'name': 'SAP Financial Integration'
}

bp = Blueprint('FSAP01', __name__, template_folder='.')
from . import views
