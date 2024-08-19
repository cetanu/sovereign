from pprint import pprint
from typing import Any, Optional

from pydantic import BaseModel

# from sovereign.utils.entry_point_loader import EntryPointLoader
from sovereign.dynamic_config.loaders import custom_loaders
from sovereign.dynamic_config.deser import deserializers


class Loadable(BaseModel):
    path: str
    protocol: str
    serialization: Optional[str] = None

    def load(self, default: Any = None) -> Any:
        try:
            loader_ = custom_loaders[self.protocol]

            ser = self.serialization
            if ser is None:
                ser = loader_.default_deser
            deserializer = deserializers[ser]

            data = loader_.load(self.path)
            return deserializer.deserialize(data)
        except Exception:
            if default is not None:
                return default
            pprint(custom_loaders.items())
            pprint(deserializers.items())
            raise ValueError(f"{self.protocol=}, {self.path=}, {self.serialization=}")

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


# custom_loaders: Dict[str, Callable[[str], Union[str, Any]]] = {}
# entry_points = EntryPointLoader("loaders")
# for entry_point in entry_points.groups["loaders"]:
#     custom_loader = entry_point.load()
#     try:
#         func = custom_loader().load
#     except AttributeError:
#         raise AttributeError("Custom loader does not implement .load()")
#     custom_loaders[entry_point.name] = func
#
# deserializers: Dict[str, Callable[[Any], Any]] = {}
# entry_points = EntryPointLoader("deserialization")
# for entry_point in entry_points.groups["deserialization"]:
#     deserializer = entry_point.load()
#     try:
#         func = deserializer().deserialize
#     except AttributeError:
#         raise AttributeError("Deserializer does not implement .deserialize()")
#     deserializers[entry_point.name] = func
