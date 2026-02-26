from flask import Blueprint

MODULE_INFO = {
    'code': 'FCN01',
    'name': 'Credit Note Management'
}

bp = Blueprint('FCN01', __name__, template_folder='.')
from . import views
