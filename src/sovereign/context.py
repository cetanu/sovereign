import asyncio
import traceback
from copy import deepcopy
from typing import (
    Any,
    Awaitable,
    Dict,
    Generator,
    Iterable,
    NamedTuple,
    NoReturn,
    Optional,
)

from fastapi import HTTPException
from structlog.stdlib import BoundLogger

from sovereign.config_loader import Loadable
from sovereign.schemas import DiscoveryRequest, XdsTemplate
from sovereign.sources import SourcePoller
from sovereign.utils.crypto import CipherContainer, CipherSuite
from sovereign.utils.timer import poll_forever, poll_forever_cron


class LoadContextResponse(NamedTuple):
    context_name: str
    context: Dict[str, Any]


class TemplateContext:
    def __init__(
        self,
        refresh_rate: Optional[int],
        refresh_cron: Optional[str],
        refresh_num_retries: int,
        refresh_retry_interval_secs: int,
        configured_context: Dict[str, Loadable],
        poller: SourcePoller,
        encryption_suite: Optional[CipherContainer],
        disabled_suite: CipherSuite,
        logger: BoundLogger,
        stats: Any,
    ) -> None:
        self.poller = poller
        self.refresh_rate = refresh_rate
        self.refresh_cron = refresh_cron
        self.refresh_num_retries = refresh_num_retries
        self.refresh_retry_interval_secs = refresh_retry_interval_secs
        self.configured_context = configured_context
        self.crypto = encryption_suite
        self.disabled_suite = disabled_suite
        self.logger = logger
        self.stats = stats
        # initial load
        self.context = asyncio.run(self.load_context_variables())

    async def start_refresh_context(self) -> NoReturn:
        if self.refresh_cron is not None:
            await poll_forever_cron(self.refresh_cron, self.refresh_context)
        elif self.refresh_rate is not None:
            await poll_forever(self.refresh_rate, self.refresh_context)

        raise RuntimeError("Failed to start refresh_context, this should never happen")

    async def refresh_context(self) -> None:
        self.context = await self.load_context_variables()

    async def _load_context(
        self,
        context_name: str,
        context_config: Loadable | str,
        refresh_num_retries: int,
        refresh_retry_interval_secs: int,
    ) -> LoadContextResponse:
        retries_left = refresh_num_retries
        context_response = {}

        while True:
            try:
                if isinstance(context_config, Loadable):
                    context_response = context_config.load()
                elif isinstance(context_config, str):
                    context_response = Loadable.from_legacy_fmt(context_config).load()
                self.stats.increment(
                    "context.refresh.success",
                    tags=[f"context:{context_name}"],
                )
                return LoadContextResponse(context_name, context_response)
            # pylint: disable=broad-except
            except Exception as e:
                retries_left -= 1
                if retries_left < 0:
                    tb = [line for line in traceback.format_exc().split("\n")]
                    self.logger.error(str(e), traceback=tb)
                    self.stats.increment(
                        "context.refresh.error",
                        tags=[f"context:{context_name}"],
                    )
                    return LoadContextResponse(context_name, context_response)
                else:
                    await asyncio.sleep(refresh_retry_interval_secs)

    async def load_context_variables(self) -> Dict[str, Any]:
        context_response: Dict[str, Any] = dict()

        context_coroutines: list[Awaitable[LoadContextResponse]] = []
        for context_name, context_config in self.configured_context.items():
            context_coroutines.append(
                self._load_context(
                    context_name,
                    context_config,
                    self.refresh_num_retries,
                    self.refresh_retry_interval_secs,
                )
            )

        context_results: list[LoadContextResponse] = await asyncio.gather(
            *context_coroutines
        )
        for context_result in context_results:
            context_response[context_result.context_name] = context_result.context

        if "crypto" not in context_response and self.crypto:
            context_response["crypto"] = self.crypto
        return context_response

    def build_new_context_from_instances(self, node_value: str) -> Dict[str, Any]:
        matches = self.poller.match_node(node_value=node_value)
        ret = dict()
        for key, value in self.context.items():
            try:
                ret[key] = deepcopy(value)
            except TypeError:
                ret[key] = value

        to_add = dict()
        for scope, instances in matches.scopes.items():
            if scope in ("default", None):
                to_add["instances"] = instances
            else:
                to_add[scope] = instances
        if to_add == {}:
            raise HTTPException(
                detail=(
                    "This node does not match any instances! ",
                    "If node matching is enabled, check that the node "
                    "match key aligns with the source match key. "
                    "If you don't know what any of this is, disable "
                    "node matching via the config",
                ),
                status_code=400,
            )
        ret.update(to_add)
        return ret

    def get_context(
        self, request: DiscoveryRequest, template: XdsTemplate
    ) -> Dict[str, Any]:
        ret = self.build_new_context_from_instances(
            node_value=self.poller.extract_node_key(request.node),
        )
        if request.hide_private_keys:
            ret["crypto"] = self.disabled_suite
        if not template.is_python_source:
            keys_to_remove = self.unused_variables(list(ret), template.jinja_variables)
            for key in keys_to_remove:
                ret.pop(key, None)
        return ret

    @staticmethod
    def unused_variables(
        keys: Iterable[str], variables: Iterable[str]
    ) -> Generator[str, None, None]:
        for key in keys:
            if key not in variables:
                yield key

    def get(self, *args: Any, **kwargs: Any) -> Any:
        return self.context.get(*args, **kwargs)
