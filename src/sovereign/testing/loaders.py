from typing import Any
from sovereign.config_loader import CustomLoader, Serialization


class Multiply(CustomLoader):
    @staticmethod
    def load(path: str, ser: Serialization) -> Any:
        result = path * 2
        return f"{ser}:{result}"
