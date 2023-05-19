import gunicorn.app.base
from fastapi import FastAPI
from typing import Optional, Dict, Any, Callable
from sovereign import asgi_config
from sovereign.app import app
from sovereign.utils.entry_point_loader import EntryPointLoader


class StandaloneApplication(gunicorn.app.base.BaseApplication):  # type: ignore
    _HOOKS = ["pre_fork", "post_fork"]

    def __init__(
        self, application: FastAPI, options: Optional[Dict[str, Any]] = None
    ) -> None:
        self.loader = EntryPointLoader(*self._HOOKS)
        self.options = options or {}
        self.application = application
        super().__init__()

    def load_config(self) -> None:
        for key, value in self.options.items():
            self.cfg.set(key.lower(), value)

        for hook in self._HOOKS:
            self._install_hooks(hook)

    def _install_hooks(self, name: str) -> None:
        hooks: list[Callable[[Any, Any], None]] = [
            ep.load() for ep in self.loader.groups[name]
        ]

        def master_hook(server: Any, worker: Any) -> None:
            for hook in hooks:
                hook(server, worker)

        self.cfg.set(name, master_hook)

    def load(self) -> FastAPI:
        return self.application


def main() -> None:
    asgi = StandaloneApplication(
        application=app, options=asgi_config.as_gunicorn_conf()
    )
    asgi.run()


if __name__ == "__main__":
    main()
