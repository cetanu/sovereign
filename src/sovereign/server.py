import warnings
import tempfile
import configparser
from pathlib import Path

import uvicorn

from sovereign import application_logger as log
from sovereign.app import app
from sovereign.worker import worker as worker_app
from sovereign.schemas import SovereignAsgiConfig, SupervisordConfig


asgi_config = SovereignAsgiConfig()
supervisord_config = SupervisordConfig()


def web() -> None:
    log.debug("Starting web server")
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
    log.debug("Starting worker")
    uvicorn.run(
        worker_app,
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
        "nodaemon": str(supervisord_config.nodaemon).lower(),
        "loglevel": supervisord_config.loglevel,
        "pidfile": supervisord_config.pidfile,
        "logfile": supervisord_config.logfile,
        "directory": supervisord_config.directory,
    }

    conf["fcgi-program:web"] = web = {
        **base,
        "socket": f"tcp://{asgi_config.host}:{asgi_config.port}",
        "numprocs": str(asgi_config.workers),
        "process_name": "%(program_name)s-%(process_num)02d",
        "command": "sovereign-web",  # default niceness, higher CPU priority
    }

    conf["program:data"] = worker = {
        **base,
        "numprocs": "1",
        "command": "nice -n 2 sovereign-worker",  # run worker with reduced CPU priority (higher niceness value)
    }

    if user := asgi_config.user:
        supervisord["user"] = user
        web["user"] = user
        worker["user"] = user

    log.debug("Writing supervisor config")
    with tempfile.NamedTemporaryFile("w", delete=False) as f:
        conf.write(f)
        log.debug("Supervisor config written out")
        return Path(f.name)


def main():
    path = write_supervisor_conf()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        from supervisor import supervisord

        log.debug("Starting processes")
        supervisord.main(["-c", path])


if __name__ == "__main__":
    main()
