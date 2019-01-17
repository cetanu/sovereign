from quart import Blueprint, redirect, url_for, send_from_directory
from pkg_resources import resource_filename


blueprint = Blueprint('docs', __name__)


@blueprint.route('/docs')
def docs_redir():
    return redirect(url_for('docs.docs', filename='index.html'))


@blueprint.route('/docs/<path:filename>')
def docs(filename):
    path = resource_filename('sovereign', 'docs')
    return send_from_directory(path, filename)
