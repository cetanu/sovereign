import tempfile
import configparser
from pathlib import Path

import uvicorn
from supervisor import supervisord

from sovereign import asgi_config
from sovereign.app import app
from sovereign.worker import worker as poller


def web() -> None:
    uvicorn.run(
        app,
        fd=0,
        log_level=asgi_config.log_level,
        access_log=False,
        timeout_keep_alive=asgi_config.keepalive,
        host=asgi_config.host,
        port=asgi_config.port,
        workers=1,  # per managed supervisor proc
    )


def worker():
    uvicorn.run(
        poller,
        log_level=asgi_config.log_level,
        access_log=False,
        timeout_keep_alive=asgi_config.keepalive,
        host="127.0.0.1",
        port=9080,
        workers=1,  # per managed supervisor proc
    )


def write_supervisor_conf() -> Path:
    proc_env = {
        "LANG": "en_US.UTF-8",
        "LC_ALL": "en_US.UTF-8",
    }
    base = {
        "autostart": "true",
        "autorestart": "true",
        "stdout_logfile": "/dev/stdout",
        "stdout_logfile_maxbytes": "0",
        "stderr_logfile": "/dev/stderr",
        "stderr_logfile_maxbytes": "0",
        "stopsignal": "QUIT",
        "environment": ",".join(["=".join((k, v)) for k, v in proc_env.items()]),
    }

    conf = configparser.RawConfigParser()
    conf["supervisord"] = supervisord = {
        "nodaemon": "true",
    }

    conf["fcgi-program:web"] = web = {
        **base,
        "socket": f"tcp://{asgi_config.host}:{asgi_config.port}",
        "numprocs": str(asgi_config.workers),
        "process_name": "%(program_name)s-%(process_num)02d",
        "command": "sovereign-web",
    }

    conf["program:data"] = worker = {
        **base,
        "numprocs": "1",
        "command": "sovereign-worker",
    }

    if user := asgi_config.user:
        supervisord["user"] = user
        web["user"] = user
        worker["user"] = user

    with tempfile.NamedTemporaryFile("w", delete=False) as f:
        conf.write(f)
        return Path(f.name)


def main():
    path = write_supervisor_conf()
    supervisord.main(["-c", path])


if __name__ == "__main__":
    main()
