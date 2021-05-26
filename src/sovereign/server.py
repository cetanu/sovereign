import gunicorn.app.base
from fastapi import FastAPI
from typing import Optional, Dict, Any
from sovereign import asgi_config
from sovereign.app import app


class StandaloneApplication(gunicorn.app.base.BaseApplication):  # type: ignore
    def __init__(
        self, application: FastAPI, options: Optional[Dict[str, Any]] = None
    ) -> None:
        self.options = options or {}
        self.application = application
        super().__init__()

    def load_config(self) -> None:
        for key, value in self.options.items():
            self.cfg.set(key.lower(), value)

    def load(self) -> FastAPI:
        return self.application


def main() -> None:
    asgi = StandaloneApplication(
        application=app, options=asgi_config.as_gunicorn_conf()
    )
    asgi.run()


if __name__ == "__main__":
    main()
