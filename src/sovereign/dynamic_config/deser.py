import json
from typing import Any, Protocol

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


class ConfigDeserializer(Protocol):
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

    def deserialize(self, input: Any) -> Any: ...


class YamlDeserializer(ConfigDeserializer):
    def deserialize(self, input: Any) -> Any:
        return yaml.safe_load(input)


class JsonDeserializer(ConfigDeserializer):
    def deserialize(self, input: Any) -> Any:
        return json.loads(input)


class JinjaDeserializer(ConfigDeserializer):
    def deserialize(self, input: Any) -> Any:
        return jinja_env.from_string(input)


class StringDeserializer(ConfigDeserializer):
    def deserialize(self, input: Any) -> Any:
        return str(input)


class PassthroughDeserializer(ConfigDeserializer):
    def deserialize(self, input: Any) -> Any:
        return input


class UjsonDeserializer(ConfigDeserializer):
    def deserialize(self, input: Any) -> Any:
        if not UJSON_AVAILABLE:
            raise ImportError("Configured a UJSON deserializer but it's not installed")
        return ujson.loads(input)


class OrjsonDeserializer(ConfigDeserializer):
    def deserialize(self, input: Any) -> Any:
        if not ORJSON_AVAILABLE:
            raise ImportError(
                "Configured an ORJSON deserializer but it's not installed"
            )
        return orjson.loads(input)
