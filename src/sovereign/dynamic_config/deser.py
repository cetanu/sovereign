import json
from typing import Any, Dict, Protocol, _ProtocolMeta

import yaml
import jinja2

try:
    import ujson

    UJSON_AVAILABLE = True
except ImportError:
    UJSON_AVAILABLE = False

try:
    import orjson

    ORJSON_AVAILABLE = True
except ImportError:
    ORJSON_AVAILABLE = False

jinja_env = jinja2.Environment(autoescape=True)


deserializers: Dict[str, "ConfigDeserializer"] = {}


class AutoRegister(_ProtocolMeta, type):
    def __new__(cls, name, bases, dct, *args, **kwargs):
        cls = super().__new__(cls, name, bases, dct)
        if bases:
            key = getattr(cls, "name", name)
            if key != name:
                # Only register if name is provided.
                # this avoids registering base classes
                deserializers[key] = cls()
        return cls


class BaseConfigDeserializer(Protocol, metaclass=AutoRegister):
    pass


class ConfigDeserializer(BaseConfigDeserializer):
    """
    Deserializers can be added to sovereign by creating a subclass
    and then specified in config:

    template_context:
      context:
          ...:
            protocol: ...
            serialization: <serializer name>
            path: ...
    """

    def deserialize(self, input: Any) -> Any:
        ...


class YamlDeserializer(ConfigDeserializer):
    name = "yaml"

    def deserialize(self, input: Any) -> Any:
        return yaml.safe_load(input)


class JsonDeserializer(ConfigDeserializer):
    name = "json"

    def deserialize(self, input: Any) -> Any:
        return json.loads(input)


class JinjaDeserializer(ConfigDeserializer):
    name = "jinja"

    def deserialize(self, input: Any) -> Any:
        return jinja_env.from_string(input)


class Jinja2Deserializer(JinjaDeserializer):
    name = "jinja2"


class StringDeserializer(ConfigDeserializer):
    name = "string"

    def deserialize(self, input: Any) -> Any:
        return str(input)


class PassthroughDeserializer(ConfigDeserializer):
    name = "raw"

    def deserialize(self, input: Any) -> Any:
        return input


class UjsonDeserializer(ConfigDeserializer):
    name = "ujson"

    def deserialize(self, input: Any) -> Any:
        if not UJSON_AVAILABLE:
            raise ImportError("Configured a UJSON deserializer but it's not installed")
        return ujson.loads(input)


class OrjsonDeserializer(ConfigDeserializer):
    name = "orjson"

    def deserialize(self, input: Any) -> Any:
        if not ORJSON_AVAILABLE:
            raise ImportError(
                "Configured an ORJSON deserializer but it's not installed"
            )
        return orjson.loads(input)
