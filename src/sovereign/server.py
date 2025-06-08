from __future__ import annotations

import sys
import tempfile
from textwrap import dedent

import uvicorn
from supervisor import supervisord

from sovereign import asgi_config
from sovereign.app import app


def uvicorn_entrypoint() -> None:
    """Run a single uvicorn instance using FD 0 for the socket."""
    uvicorn.run(
        app,
        fd=0,
        log_level=asgi_config.log_level,
        access_log=False,
    )


def make_supervisor_conf() -> str:
    command = f"{sys.executable} -m sovereign.server uvicorn"
    return dedent(
        f"""
        [supervisord]
        nodaemon=true

        [fcgi-program:uvicorn]
        socket=tcp://{asgi_config.host}:{asgi_config.port}
        command={command}
        numprocs={asgi_config.workers}
        process_name=uvicorn-%(process_num)d
        stdout_logfile=/dev/stdout
        stdout_logfile_maxbytes=0
        """
    )


def main() -> None:
    conf = make_supervisor_conf()
    with tempfile.NamedTemporaryFile("w", delete=False) as f:
        f.write(conf)
        path = f.name
    supervisord.main(["-c", path])


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "uvicorn":
        uvicorn_entrypoint()
    else:
        main()
