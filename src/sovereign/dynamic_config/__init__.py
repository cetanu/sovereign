import inspect
from typing import Any, Dict, Optional

from pydantic import BaseModel

from sovereign.utils.entry_point_loader import EntryPointLoader
from sovereign.dynamic_config.loaders import CustomLoader
from sovereign.dynamic_config.deser import ConfigDeserializer


class Loadable(BaseModel):
    path: str
    protocol: str
    serialization: Optional[str] = None

    def load(self, default: Any = None) -> Any:
        if self.protocol not in LOADERS:
            raise KeyError(
                f"Could not find CustomLoader {self.protocol}. Available: {LOADERS}"
            )
        loader_ = LOADERS[self.protocol]

        ser = self.serialization
        if ser is None:
            ser = loader_.default_deser
        if ser not in DESERIALIZERS:
            raise KeyError(
                f"Could not find Deserializer {ser}. Available: {DESERIALIZERS}"
            )
        deserializer = DESERIALIZERS[ser]

        try:
            data = loader_.load(self.path)
            return deserializer.deserialize(data)
        except Exception as original_error:
            if default is not None:
                return default
            raise Exception(
                f"{self.protocol=}, {self.path=}, {self.serialization=}, {original_error=}"
            )

    @staticmethod
    def from_legacy_fmt(fmt_string: str) -> "Loadable":
        if "://" not in fmt_string:
            return Loadable(protocol="inline", serialization="string", path=fmt_string)
        try:
            scheme, path = fmt_string.split("://")
        except ValueError:
            raise ValueError(fmt_string)
        try:
            proto, ser = scheme.split("+")
        except ValueError:
            proto, ser = scheme, "yaml"

        if proto in ("python", "module"):
            ser = "raw"
        if proto in ("http", "https"):
            path = "://".join([proto, path])

        return Loadable(
            protocol=proto,
            serialization=ser,
            path=path,
        )


LOADERS: Dict[str, CustomLoader] = {}
for entry_point in EntryPointLoader("loaders").groups["loaders"]:
    custom_loader = entry_point.load()
    func = custom_loader()
    method = getattr(func, "load")
    if not inspect.ismethod(method):
        raise AttributeError(
            f"CustomLoader {entry_point.name} does not implement .load()"
        )
    LOADERS[entry_point.name] = func


DESERIALIZERS: Dict[str, ConfigDeserializer] = {}
for entry_point in EntryPointLoader("deserializers").groups["deserializers"]:
    deserializer = entry_point.load()
    func = deserializer()
    method = getattr(func, "deserialize")
    if not inspect.ismethod(method):
        raise AttributeError(
            f"Deserializer {entry_point.name} does not implement .deserialize()"
        )
    DESERIALIZERS[entry_point.name] = func
