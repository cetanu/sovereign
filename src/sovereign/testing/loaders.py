from typing import Any
from sovereign.dynamic_config.loaders import CustomLoader


class Multiply(CustomLoader):
    def load(self, path: str) -> Any:
        result = path * 2
        return result
