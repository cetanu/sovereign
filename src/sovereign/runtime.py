import json
from typing import Any
from sovereign.constants import TEMPLATE_CTX_PATH


def template_context() -> Any:
    with open(TEMPLATE_CTX_PATH) as f:
        return json.loads(f.read())
