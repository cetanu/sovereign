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
from sovereign import config_loader
from sovereign.utils.entry_point_loader import EntryPointLoader
from structlog.stdlib import BoundLogger

from sovereign.config_loader import Loadable
from sovereign.schemas import DiscoveryRequest, EncryptionConfig, XdsTemplate
from sovereign.sources import SourcePoller
from sovereign.utils.crypto.crypto import CipherContainer
from sovereign.utils.crypto.suites import EncryptionType
from sovereign.utils.timer import poll_forever, poll_forever_cron


class LoadContextResponse(NamedTuple):
    context_name: str
    context: Dict[str, Any]
    success: bool = True


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
        logger: BoundLogger,
        stats: Any,
    ) -> None:
        self.poller = poller
        self.refresh_rate = refresh_rate
        self.refresh_cron = refresh_cron
        self.refresh_num_retries = refresh_num_retries
        self.refresh_retry_interval_secs = refresh_retry_interval_secs
        self.configured_context = configured_context
        self.crypto: CipherContainer | None = encryption_suite
        self.logger = logger
        self.stats = stats
        # initial load
        self.context: Dict[str, Any] = {}
        entry_points = EntryPointLoader("loaders")
        for entry_point in entry_points.groups["loaders"]:
            custom_loader = entry_point.load()
            try:
                func = custom_loader.load
            except AttributeError:
                raise AttributeError("Custom loader does not implement .load()")
            config_loader.loaders[entry_point.name] = func
        asyncio.run(self.load_context_variables())

    async def start_refresh_context(self) -> NoReturn:
        if self.refresh_cron is not None:
            await poll_forever_cron(self.refresh_cron, self.refresh_context)
        elif self.refresh_rate is not None:
            await poll_forever(self.refresh_rate, self.refresh_context)
        raise RuntimeError("Failed to start refresh_context, this should never happen")

    async def refresh_context(self) -> None:
        await self.load_context_variables()

    async def _load_context(
        self,
        name: str,
        loader: Loadable | str,
        refresh_num_retries: int,
        refresh_retry_interval_secs: int,
    ) -> LoadContextResponse:
        retries_left = refresh_num_retries
        response = {}

        while True:
            try:
                if isinstance(loader, Loadable):
                    response = loader.load()
                elif isinstance(loader, str):
                    response = Loadable.from_legacy_fmt(loader).load()
                self.stats.increment(
                    "context.refresh.success",
                    tags=[f"context:{name}"],
                )
                return LoadContextResponse(name, response)
            # pylint: disable=broad-except
            except Exception as e:
                retries_left -= 1
                if retries_left < 0:
                    tb = [line for line in traceback.format_exc().split("\n")]
                    self.logger.error(str(e), traceback=tb)
                    self.stats.increment(
                        "context.refresh.error",
                        tags=[f"context:{name}"],
                    )
                    return LoadContextResponse(name, response, False)
                else:
                    await asyncio.sleep(refresh_retry_interval_secs)

    async def load_context_variables(self) -> None:
        coroutines: list[Awaitable[LoadContextResponse]] = []
        for name, conf in self.configured_context.items():
            coroutines.append(
                self._load_context(
                    name,
                    conf,
                    self.refresh_num_retries,
                    self.refresh_retry_interval_secs,
                )
            )

        results: list[LoadContextResponse] = await asyncio.gather(*coroutines)

        for res in results:
            if res.success or res.context_name not in self.context:
                self.context[res.context_name] = res.context

        if "crypto" not in self.context and self.crypto:
            self.context["crypto"] = self.crypto

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
        ret["__hide_from_ui"] = lambda v: v
        if request.hide_private_keys:
            ret["__hide_from_ui"] = lambda _: "(value hidden)"
            ret["crypto"] = CipherContainer.from_encryption_configs(
                encryption_configs=[EncryptionConfig("", EncryptionType.DISABLED)],
                logger=self.logger,
            )
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
