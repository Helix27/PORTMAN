from flask import Blueprint

MODULE_INFO = {
    'code': 'SAPCFG',
    'name': 'SAP API Configuration'
}

bp = Blueprint('SAPCFG', __name__, template_folder='.')
from . import views
