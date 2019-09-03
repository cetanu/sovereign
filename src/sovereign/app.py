import os
import json
import time
import schedule
import traceback
from datetime import datetime, timedelta, date
from flask_log_request_id import RequestID, current_request_id
from quart import Quart, g, request, jsonify, redirect, url_for, make_response, Response

from sovereign import statsd, config, __versionstr__
from sovereign.sources import refresh
from sovereign.logs import LOG
from sovereign.views import (
    crypto,
    discovery,
    healthchecks,
    admin,
)

try:
    import sentry_sdk
    from sentry_asgi import SentryMiddleware
except ImportError:
    sentry_sdk = None
    SentryMiddleware = None


class JSONEncoder(json.JSONEncoder):
    def default(self, object_):
        if isinstance(object_, date):
            return object_.isoformat()
        if hasattr(object_, '__html__'):
            return str(object_.__html__())
        try:
            return super().default(object_)
        except TypeError:
            return str(object_)


def init_app():
    # Warm the sources once before starting
    refresh()

    application: Quart = Quart(__name__)
    application.json_encoder = JSONEncoder
    RequestID(application)

    application.config['JSONIFY_PRETTYPRINT_REGULAR'] = True
    application.config['SERVER_NAME'] = f'Sovereign ({__versionstr__})'
    application.host = os.getenv('SOVEREIGN_HOST', '0.0.0.0')
    application.port = int(os.getenv('SOVEREIGN_PORT', '8080'))

    application.register_blueprint(admin.blueprint)
    application.register_blueprint(discovery.blueprint)
    application.register_blueprint(healthchecks.blueprint)
    application.register_blueprint(crypto.blueprint)

    for handler in application.logger.handlers:
        application.logger.removeHandler(handler)

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
            env=config.environment,
            worker_pid=os.getpid()
        )

    @application.errorhandler(Exception)
    def exception_handler(e: Exception):
        error = {
            'error': str(e),
            'request_id': current_request_id()
        }
        if config.debug_enabled:
            error['traceback'] = [line for line in traceback.format_exc().split('\n')]
        g.log = g.log.bind(**error)
        status_code = getattr(e, 'status', getattr(e, 'code', 500))
        return jsonify(error), status_code

    @application.after_request
    def log_request(response: Response):
        duration = g.request_time()
        g.log.msg(
            code=response.status_code,
            duration=duration,
            bytes_out=response.content_length,
            bytes_in=request.content_length
        )
        if 'discovery' in str(request.endpoint):
            tags = [
                f'path:{request.path}',
                f'code:{response.status_code}',
            ]
            statsd.timing('rq_ms', value=duration, tags=tags)
        return response

    @application.teardown_request
    def run_scheduled_tasks(exc=None):
        if isinstance(exc, Exception):
            raise exc
        schedule.run_pending()

    if config.sentry_dsn and sentry_sdk:
        sentry_sdk.init(config.sentry_dsn)
        application = SentryMiddleware(application)

    return application


app = init_app()


if __name__ == '__main__':
    app.run(host='localhost', port=8080)
