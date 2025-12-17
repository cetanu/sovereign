import inspect
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from sovereign.dynamic_config.deser import ConfigDeserializer
from sovereign.dynamic_config.loaders import CustomLoader
from sovereign.utils.entry_point_loader import EntryPointLoader

LOADERS: dict[str, CustomLoader] = {}
DESERIALIZERS: dict[str, ConfigDeserializer] = {}


class Loadable(BaseModel):
    path: str = Field(alias="target")
    protocol: str = Field(alias="loader")
    serialization: str | None = Field(None, alias="deserialize_with")
    interval: str | None = None
    retry_policy: dict[str, Any] | None = None

    model_config = ConfigDict(populate_by_name=True)

    def load(self, default: Any = None) -> Any:
        global LOADERS
        if not LOADERS:
            init_loaders()

        global DESERIALIZERS
        if not DESERIALIZERS:
            init_deserializers()

        if self.protocol not in LOADERS:
            raise KeyError(
                f"Could not find CustomLoader {self.protocol}. Available: {LOADERS}"
            )
        loader = LOADERS[self.protocol]

        ser = self.serialization
        if ser is None:
            ser = loader.default_deser
        elif ser not in DESERIALIZERS:
            raise KeyError(
                f"Could not find Deserializer {ser}. Available: {DESERIALIZERS}"
            )
        deserializer = DESERIALIZERS[ser]

        try:
            data = loader.load(self.path)
            return deserializer.deserialize(data)
        except Exception as original_error:
            if default is not None:
                return default
            raise Exception(
                f"Could not load value. {self.__str__()}, {original_error=}"
            )

    @staticmethod
    def from_legacy_fmt(fmt_string: str) -> "Loadable":
        if "://" not in fmt_string:
            return Loadable(
                loader="inline",
                deserialize_with="string",
                target=fmt_string,
            )
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
            loader=proto,
            deserialize_with=ser,
            target=path,
        )

    def __str__(self) -> str:
        return f"Loadable({self.protocol}+{self.serialization}://{self.path})"


def init_loaders():
    global LOADERS
    for entry_point in EntryPointLoader("loaders").groups["loaders"]:
        custom_loader = entry_point.load()
        func = custom_loader()
        method = getattr(func, "load")
        if not inspect.ismethod(method):
            raise AttributeError(
                f"CustomLoader {entry_point.name} does not implement .load()"
            )
        LOADERS[entry_point.name] = func


def init_deserializers():
    global DESERIALIZERS
    for entry_point in EntryPointLoader("deserializers").groups["deserializers"]:
        deserializer = entry_point.load()
        func = deserializer()
        method = getattr(func, "deserialize")
        if not inspect.ismethod(method):
            raise AttributeError(
                f"Deserializer {entry_point.name} does not implement .deserialize()"
            )
        DESERIALIZERS[entry_point.name] = func
