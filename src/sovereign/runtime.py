import json
from typing import Any

from cachelib import SimpleCache

from sovereign.constants import TEMPLATE_CTX_PATH

_cache = SimpleCache(threshold=5, default_timeout=30)

def template_context() -> Any:
    ctx = _cache.get("template_context")
    if ctx is not None:
        return ctx
    with open(TEMPLATE_CTX_PATH) as f:
        ret = json.loads(f.read())
        _cache.set("template_context", ret)
        return ret
