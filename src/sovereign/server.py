import threading
import time

import gunicorn.app.base
import schedule

from sovereign import asgi_config, config
from sovereign.app import app


class StandaloneApplication(gunicorn.app.base.BaseApplication):
    def __init__(self, application, options=None):
        self.options = options or {}
        self.application = application
        super().__init__()

    def load_config(self):
        for key, value in self.options.items():
            self.cfg.set(key.lower(), value)

    def load(self):
        return self.application


def main():
    cease_continuous_run = threading.Event()

    class ScheduleThread(threading.Thread):
        @classmethod
        def run(cls):
            while not cease_continuous_run.is_set():
                schedule.run_pending()
                time.sleep(config.sources_refresh_rate)

    continuous_thread = ScheduleThread()
    continuous_thread.start()

    asgi = StandaloneApplication(
        application=app,
        options=asgi_config.as_gunicorn_conf()
    )
    asgi.run()


if __name__ == '__main__':
    main()
