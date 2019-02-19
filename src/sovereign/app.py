import os
import time
import traceback
from datetime import datetime, timedelta
import quart.flask_patch
from quart import (
    Quart,
    g,
    request,
    jsonify,
    redirect,
    url_for,
    make_response
)
from flask_log_request_id import RequestID, current_request_id
from sovereign import statsd, ENVIRONMENT
from sovereign.logs import LOG
from sovereign.views import (
    crypto,
    discovery,
    healthchecks,
    admin,
)


def init_app():
    application: Quart = Quart(__name__)
    RequestID(application)

    application.config['JSONIFY_PRETTYPRINT_REGULAR'] = True
    application.config['RESPONSE_TIMEOUT'] = 5
    application.config['BODY_TIMEOUT'] = 5
    application.config['MAX_CONTENT_LENGTH'] = 1024 * 4
    application.host = os.getenv('SOVEREIGN_HOST', '0.0.0.0')
    application.port = int(os.getenv('SOVEREIGN_PORT', '8080'))

    application.register_blueprint(admin.blueprint)
    application.register_blueprint(discovery.blueprint)
    application.register_blueprint(healthchecks.blueprint)
    application.register_blueprint(crypto.blueprint)

    for handler in application.logger.handlers:
        application.logger.removeHandler(handler)

    # pylint: disable=unused-variable

    @application.route('/')
    def index():
        return redirect(url_for('admin.display_config'))

    @application.route('/favicon.ico')
    async def favicon_stub():
        expiry_time = datetime.utcnow() + timedelta(weeks=4)
        body, status, headers = (
            '', 200,
            {'Expires': expiry_time.strftime("%a, %d %b %Y %H:%M:%S GMT")}
        )
        response = await make_response(body, status, headers)
        return response

    @application.before_request
    def time_request():
        g.request_start_time = time.time()
        g.request_time = lambda: (time.time() - g.request_start_time) * 1000  # Milliseconds

    @application.before_request
    def add_logger():
        g.log = LOG.bind(
            uri_path=request.path,
            uri_query=request.query_string or '-',
            src_ip=request.remote_addr,
            site=request.headers.get('host', '-'),
            method=request.method,
            user_agent=request.headers.get('user-agent', '-'),
            request_id=current_request_id(),
            env=ENVIRONMENT,
            worker_pid=os.getpid()
        )

    @application.errorhandler(Exception)
    def exception_handler(e: Exception):
        error = {
            'error': repr(e),
            'request_id': current_request_id(),
            'traceback': traceback.format_exc()
        }
        g.log = g.log.bind(**error)
        return jsonify(error), getattr(e, 'status', 500)

    @application.after_request
    def log_request(response):
        duration = g.request_time()
        g.log.msg(
            code=response.status_code,
            duration=duration
        )
        if 'discovery' in str(request.endpoint):
            tags = [
                f'path:{request.path}',
                f'code:{response.status_code}',
            ]
            statsd.timing('rq_ms', value=duration, tags=tags)
        return response

    return application


assert quart.flask_patch
app = init_app()


if __name__ == '__main__':
    app.run(host='localhost', port=8080)
