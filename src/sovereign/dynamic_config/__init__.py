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
        if self.protocol not in custom_loaders:
            raise KeyError(
                f"Could not find CustomLoader {self.protocol}. Available: {custom_loaders}"
            )
        loader_ = custom_loaders[self.protocol]

        ser = self.serialization
        if ser is None:
            ser = loader_.default_deser
        if ser not in deserializers:
            raise KeyError(
                f"Could not find Deserializer {ser}. Available: {deserializers}"
            )
        deserializer = deserializers[ser]

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


custom_loaders: Dict[str, CustomLoader] = {}
loader_entry_point = EntryPointLoader("loaders")
for entry_point in loader_entry_point.groups["loaders"]:
    custom_loader = entry_point.load()
    try:
        func = custom_loader()
    except AttributeError:
        raise AttributeError("CustomLoader does not implement .load()")
    custom_loaders[entry_point.name] = func


deserializers: Dict[str, ConfigDeserializer] = {}
deser_entry_point = EntryPointLoader("deserializers")
for entry_point in deser_entry_point.groups["deserializers"]:
    deserializer = entry_point.load()
    try:
        func = deserializer()
    except AttributeError:
        raise AttributeError("Deserializer does not implement .deserialize()")
    deserializers[entry_point.name] = func
