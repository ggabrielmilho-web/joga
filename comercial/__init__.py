from flask import Blueprint

comercial_bp = Blueprint(
    'comercial', __name__,
    template_folder='templates',
)

from . import routes  # noqa: E402,F401
