import gunicorn.app.base
from sovereign import asgi_config
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
    asgi = StandaloneApplication(
        application=app,
        options=asgi_config.as_gunicorn_conf()
    )
    asgi.run()


if __name__ == '__main__':
    main()
