from flask import Blueprint

MODULE_INFO = {
    'code': 'FIN01',
    'name': 'Billing & Invoicing'
}

bp = Blueprint('FIN01', __name__, template_folder='.')

from . import views
