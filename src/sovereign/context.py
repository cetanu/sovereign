import json
import fcntl
import traceback
from typing import Dict, Any, NoReturn, Optional
from copy import deepcopy
from fastapi import HTTPException
from fastapi.encoders import jsonable_encoder
from sovereign.config_loader import Loadable
from sovereign.schemas import Node
from sovereign.sources import SourcePoller
from sovereign.utils.crypto import CipherSuite, CipherContainer
from sovereign.utils.timer import poll_forever, poll_forever_cron
from sovereign.constants import TEMPLATE_CTX_PATH
from structlog.stdlib import BoundLogger


def attempt_serialization(o):  # type: ignore
    try:
        return jsonable_encoder(o)
    # pylint: disable=broad-except
    except Exception as e:
        return f"could not serialize context: {e}"


class TemplateContext:
    def __init__(
        self,
        refresh_rate: Optional[int],
        refresh_cron: Optional[str],
        configured_context: Dict[str, Loadable],
        poller: SourcePoller,
        encryption_suite: CipherContainer,
        disabled_suite: CipherSuite,
        logger: BoundLogger,
        stats: Any,
    ) -> None:
        self.poller = poller
        self.refresh_rate = refresh_rate
        self.refresh_cron = refresh_cron
        self.configured_context = configured_context
        self.crypto = encryption_suite
        self.disabled_suite = disabled_suite
        self.logger = logger
        self.stats = stats
        # initial load
        self.context = self.load_context_variables()

    async def start_refresh_context(self) -> NoReturn:
        if self.refresh_cron is not None:
            await poll_forever_cron(self.refresh_cron, self.refresh_context)
        elif self.refresh_rate is not None:
            await poll_forever(self.refresh_rate, self.refresh_context)

        raise RuntimeError("Failed to start refresh_context, this should never happen")

    async def refresh_context(self) -> None:
        self.context = self.load_context_variables()
        with open(TEMPLATE_CTX_PATH, "a") as handle:
            try:
                # Lock
                fcntl.flock(handle, fcntl.LOCK_EX)
                # Save
                with open(TEMPLATE_CTX_PATH, "w") as savefile:
                    json.dump(self.context, savefile, default=attempt_serialization)
            except BlockingIOError:
                # TODO: metrics?
                pass
            finally:
                # Unlock
                fcntl.flock(handle, fcntl.LOCK_UN)

    def load_context_variables(self) -> Dict[str, Any]:
        ret = dict()
        for k, v in self.configured_context.items():
            try:
                if isinstance(v, Loadable):
                    ret[k] = v.load()
                elif isinstance(v, str):
                    ret[k] = Loadable.from_legacy_fmt(v).load()
                self.stats.increment(
                    "context.refresh.success",
                    tags=[f"context:{k}"],
                )
            except Exception as e:  # pylint: disable=broad-exception-caught
                tb = [line for line in traceback.format_exc().split("\n")]
                self.logger.error(str(e), traceback=tb)
                self.stats.increment(
                    "context.refresh.error",
                    tags=[f"context:{k}"],
                )
        return ret

    def get_context(self, node: Node) -> Dict[str, Any]:
        node_value = self.poller.extract_node_key(node)

        # Add current template context
        ret = dict()
        for key, value in self.context.items():
            try:
                ret[key] = deepcopy(value)
            except TypeError:
                ret[key] = value

        # Add matched instances
        to_add = dict()
        matches = self.poller.match_node(node_value=node_value)
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
        ret["crypto"] = self.crypto
        return ret
