import schedule
from typing import Dict, Any, Generator, Iterable
from copy import deepcopy
from fastapi import HTTPException
from sovereign import config, poller
from sovereign.config_loader import Loadable
from sovereign.schemas import DiscoveryRequest, XdsTemplate
from sovereign.utils import crypto
from sovereign.utils.crypto import disabled_suite

REFRESH_RATE = config.template_context.refresh_rate
REFRESH_ENABLED = config.template_context.refresh
CONFIGURED_CONTEXT = config.template_context.context


class TemplateContext:
    def __init__(self) -> None:
        self.context = self.load_context_variables()
        self.refresh_context()  # One-time setup
        if REFRESH_ENABLED:
            # Continuous re-loading of context variables
            schedule.every(REFRESH_RATE).seconds.do(self.refresh_context)

    def refresh_context(self) -> None:
        self.context = self.load_context_variables()

    @staticmethod
    def load_context_variables() -> Dict[str, Any]:
        ret = dict()
        for k, v in CONFIGURED_CONTEXT.items():
            if isinstance(v, Loadable):
                ret[k] = v.load()
            elif isinstance(v, str):
                ret[k] = Loadable.from_legacy_fmt(v).load()
        if "crypto" not in ret:
            ret["crypto"] = crypto
        return ret

    def build_new_context_from_instances(self, node_value: str) -> Dict[str, Any]:
        matches = poller.match_node(node_value=node_value)
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

    def safe(self, request: DiscoveryRequest) -> Dict[str, Any]:
        ret = self.build_new_context_from_instances(
            node_value=poller.extract_node_key(request.node),
        )
        # If the discovery request came from a mock, it will
        # typically contain this metadata key.
        # This means we should prevent any decryptable data
        # from ending up in the response.
        if request.hide_private_keys:
            ret["crypto"] = disabled_suite
        return ret

    def get_context(
        self, request: DiscoveryRequest, template: XdsTemplate
    ) -> Dict[str, Any]:
        ret = self.safe(request)
        if not template.is_python_source:
            keys_to_remove = self.unused_variables(
                list(ret), template.jinja_variables()
            )
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


template_context = TemplateContext()
poller.lazy_load_modifiers(config.modifiers)
poller.lazy_load_global_modifiers(config.global_modifiers)
