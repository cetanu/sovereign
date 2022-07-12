from typing import Dict, Any, Generator, Iterable, NoReturn, Optional
from copy import deepcopy
from fastapi import HTTPException
from sovereign.config_loader import Loadable
from sovereign.schemas import DiscoveryRequest, XdsTemplate
from sovereign.sources import SourcePoller
from sovereign.utils.crypto import CipherSuite
from sovereign.utils.timer import poll_forever, poll_forever_cron


class TemplateContext:
    def __init__(
        self,
        refresh_rate: Optional[int],
        refresh_cron: Optional[str],
        configured_context: Dict[str, Loadable],
        poller: SourcePoller,
        encryption_suite: CipherSuite,
        disabled_suite: CipherSuite,
        logger: Any,
        stats: Any,
    ) -> None:
        self.poller = poller
        self.refresh_rate = refresh_rate
        self.refresh_cron = refresh_cron
        self.configured_context = configured_context
        self.crypto = encryption_suite
        self.disabled_suite = disabled_suite
        # initial load
        self.context = self.load_context_variables()
        self.logger = logger
        self.stats = stats

    async def start_refresh_context(self) -> NoReturn:
        if self.refresh_cron is not None:
            await poll_forever_cron(self.refresh_cron, self.refresh_context)
        elif self.refresh_rate is not None:
            await poll_forever(self.refresh_rate, self.refresh_context)

        raise RuntimeError("Failed to start refresh_context, this should never happen")

    async def refresh_context(self) -> None:
        try:
            self.context = self.load_context_variables()
            self.stats.increment("context.refresh.success")
        # pylint: disable=broad-except
        except Exception as e:
            self.logger(event=e)
            self.stats.increment("context.refresh.error")

    def load_context_variables(self) -> Dict[str, Any]:
        ret = dict()
        for k, v in self.configured_context.items():
            if isinstance(v, Loadable):
                ret[k] = v.load()
            elif isinstance(v, str):
                ret[k] = Loadable.from_legacy_fmt(v).load()
        if "crypto" not in ret:
            ret["crypto"] = self.crypto
        return ret

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
