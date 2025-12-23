import datetime
import time
import zlib
from typing import Any

from croniter import croniter

from sovereign.configuration import SovereignConfigv2
from sovereign.context import CronInterval, SecondsInterval, TaskInterval
from sovereign.dynamic_config import Loadable
from sovereign.utils.timer import wait_until
from sovereign.v2.data.repositories import ContextRepository, DiscoveryEntryRepository
from sovereign.v2.data.worker_queue import QueueProtocol
from sovereign.v2.types import Context, RenderDiscoveryJob


def refresh_context(
    name: str,
    config: SovereignConfigv2,
    context_repository: ContextRepository,
    discovery_job_repository: DiscoveryEntryRepository,
    queue: QueueProtocol,
):
    loadable = config.template_context.context[name]

    try:
        value: Any = loadable.load()
        context_hash = _get_hash(value)

        if context_repository.get_hash(name) != context_hash:
            context = Context(
                name=name,
                data=value,
                data_hash=context_hash,
                refresh_after=get_refresh_after(config, loadable),
            )
            context_repository.save(context)

            request_hashes: set[str] = set()

            for version, version_templates in config.templates.versions.items():
                for template in version_templates:
                    if name in template.depends_on:
                        for request_hash in discovery_job_repository.find_all_request_hashes_by_template(
                            template.type
                        ):
                            request_hashes.add(request_hash)

            for request_hash in request_hashes:
                print(
                    "Queuing render for discovery request:",
                    request_hash,
                    "because context",
                    name,
                    "changed",
                )
                queue.put(RenderDiscoveryJob(request_hash=request_hash))
    except Exception:
        # todo: handle exceptions/retries
        print("Failed to load context:", name)
        pass


def _get_hash(value: Any) -> int:
    # todo: when we create the `Context` object for use in our data store,
    # move this to __hash__()
    data: bytes = repr(value).encode()
    return zlib.adler32(data) & 0xFFFFFFFF


# noinspection PyUnreachableCode
def _seconds_til_next_run(task_interval: TaskInterval) -> int:
    match task_interval.value:
        case CronInterval(cron=expression):
            cron = croniter(expression)
            next_date = cron.get_next(datetime.datetime)
            return int(wait_until(next_date))
        case SecondsInterval(seconds=seconds):
            return seconds
        case _:
            return 0


def get_refresh_after(config: SovereignConfigv2, loadable: Loadable) -> int:
    interval = loadable.interval

    # get the default interval from config if not specified in loadable
    if interval is None:
        template_context_config = config.template_context
        if template_context_config.refresh_rate is not None:
            interval = str(template_context_config.refresh_rate)
        elif template_context_config.refresh_cron is not None:
            interval = template_context_config.refresh_cron
        else:
            interval = "60"

    task_interval = TaskInterval.from_str(interval)

    return int(time.time() + _seconds_til_next_run(task_interval))
