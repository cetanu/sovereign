import hashlib
import importlib
from functools import cached_property
from types import ModuleType

import jmespath
from jinja2 import Template
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    computed_field,
)
from typing_extensions import Any, cast

from sovereign.dynamic_config import Loadable
from sovereign.utils.version_info import compute_hash

missing_arguments = {"missing", "positional", "arguments:"}


class Resources(list[str]):
    """
    Acts like a regular list except it returns True
    for all membership tests when empty.
    """

    def __contains__(self, item: object) -> bool:
        if len(self) == 0:
            return True
        return super().__contains__(item)


class Locality(BaseModel):
    region: str | None = Field(None)
    zone: str | None = Field(None)
    sub_zone: str | None = Field(None)

    def __str__(self) -> str:
        return f"{self.region}::{self.zone}::{self.sub_zone}"


class SemanticVersion(BaseModel):
    major_number: int = 0
    minor_number: int = 0
    patch: int = 0

    def __str__(self) -> str:
        return f"{self.major_number}.{self.minor_number}.{self.patch}"


class BuildVersion(BaseModel):
    version: SemanticVersion = SemanticVersion()
    metadata: dict[str, Any] = {}


class Extension(BaseModel):
    name: str | None = None
    category: str | None = None
    version: BuildVersion | None = None
    disabled: bool | None = None


class Node(BaseModel):
    id: str = Field("-", title="Hostname")
    cluster: str = Field(
        ...,
        title="Envoy service-cluster",
        description="The ``--service-cluster`` configured by the Envoy client",
    )
    metadata: dict[str, Any] = Field(default_factory=dict, title="Key:value metadata")
    # noinspection PyArgumentList
    locality: Locality = Field(Locality(), title="Locality")
    build_version: str | None = Field(
        None,  # Optional in the v3 Envoy API
        title="Envoy build/release version string",
        description="Used to identify what version of Envoy the "
        "client is running, and what config to provide in response",
    )
    user_agent_name: str = "envoy"
    user_agent_version: str = ""
    user_agent_build_version: BuildVersion = BuildVersion()
    extensions: list[Extension] = []
    client_features: list[str] = []

    @property
    def common(self) -> tuple[str, str | None, str, BuildVersion, Locality]:
        """
        Returns fields that are the same in adjacent proxies
        ie. proxies that are part of the same logical group
        """
        return (
            self.cluster,
            self.build_version,
            self.user_agent_version,
            self.user_agent_build_version,
            self.locality,
        )


class Status(BaseModel):
    code: int
    message: str
    details: list[Any]


class XdsTemplate(BaseModel):
    path: str | Loadable
    resource_type: str
    depends_on: list[str] = Field(default_factory=list)

    @property
    def loadable(self):
        if isinstance(self.path, str):
            return Loadable.from_legacy_fmt(self.path)
        elif isinstance(self.path, Loadable):
            return self.path
        raise TypeError(
            "Template path must be a loadable format. "
            "e.g. file+yaml:///etc/templates/clusters.yaml"
        )

    @property
    def is_python_source(self):
        return self.loadable.protocol == "python"

    @property
    def code(self) -> ModuleType | Template:
        return self.loadable.load()

    def generate(self, *args: Any, **kwargs: Any) -> dict[str, Any] | str | None:
        if isinstance(self.code, ModuleType):
            try:
                template_fn = self.code.call  # type: ignore
                return {"resources": list(template_fn(*args, **kwargs))}
            except TypeError as e:
                if not set(str(e).split()).issuperset(missing_arguments):
                    raise ValueError(
                        f"Tried to render template '{self.resource_type}'. "
                        f"Error calling function: {str(e)}"
                    )
                message_start = str(e).find(":")
                missing_args = str(e)[message_start + 2 :]
                supplied_args = list(kwargs.keys())
                raise TypeError(
                    f"Tried to render template '{self.resource_type}' using partial arguments. "
                    f"Missing args: {missing_args}. Supplied args: {args} "
                    f"Supplied keyword args: {supplied_args}. "
                    f"Add to `depends_on` to ensure required context is provided."
                )
        else:
            return self.code.render(*args, **kwargs)

    @property
    def source(self) -> str:
        old_serialization = self.loadable.serialization
        if self.loadable.serialization in ("jinja", "jinja2"):
            # The Jinja2 template serializer does not properly set a name
            # for the loaded template.
            # The repr for the template prints out as the memory address
            # This makes it really hard to generate a consistent version_info string
            # in rendered configuration.
            # For this reason, we re-load the template as a string instead, and create a checksum.
            self.loadable.serialization = "string"
            ret = self.loadable.load()
            self.loadable.serialization = old_serialization
            return str(ret)
        elif self.is_python_source:
            # If the template specified is a python source file,
            # we can simply read and return the source of it.
            old_protocol = self.loadable.protocol
            self.loadable.protocol = "inline"
            self.loadable.serialization = "string"
            ret = self.loadable.load()
            self.loadable.protocol = old_protocol
            self.loadable.serialization = old_serialization
            return str(ret)
        ret = self.loadable.load()
        return str(ret)

    def __repr__(self) -> str:
        return f"XdsTemplate({self.loadable}, {hash(self)})"

    @computed_field  # type: ignore[prop-decorator]
    @cached_property
    def version(self) -> str:
        return compute_hash(self.source)

    def __hash__(self) -> int:
        return int(self.version)

    __str__ = __repr__


class DiscoveryRequest(BaseModel):
    # Actual envoy fields
    node: Node = Field(..., title="Node information about the envoy proxy")
    version_info: str = Field(
        "0", title="The version of the envoy clients current configuration"
    )
    resource_names: list[str] = Field(
        default_factory=list, title="list of requested resource names"
    )
    error_detail: Status | None = Field(
        None, title="Error details from the previous xDS request"
    )
    # Internal fields for sovereign
    is_internal_request: bool = False
    type_url: str | None = Field(
        None, title="The corresponding type_url for the requested resource"
    )
    resource_type: str | None = Field(None, title="Resource type requested")
    api_version: str | None = Field(None, title="Envoy API version (v2/v3/etc)")
    desired_controlplane: str | None = Field(
        None, title="The host header provided in the Discovery Request"
    )
    # Pydantic
    model_config = ConfigDict(extra="ignore")

    @computed_field  # type: ignore[prop-decorator]
    @cached_property
    def envoy_version(self) -> str:
        try:
            version = str(self.node.user_agent_build_version.version)
            assert version != "0.0.0"
        except AssertionError:
            try:
                build_version = self.node.build_version
                if build_version is None:
                    return "default"
                _, version, *_ = build_version.split("/")
            except (AttributeError, ValueError):
                # TODO: log/metric this?
                return "default"
        return version

    @property
    def resources(self) -> Resources:
        return Resources(self.resource_names)

    # noinspection PyShadowingBuiltins
    def cache_key(self, rules: list[str]) -> str:
        map = self.model_dump()
        hash = hashlib.sha256()
        for expr in sorted(rules):
            value = cast(str, jmespath.search(expr, map))
            val_str = f"{expr}={repr(value)}"
            hash.update(val_str.encode())
        return hash.hexdigest()

    @computed_field  # type: ignore[misc]
    @property
    def template(self) -> XdsTemplate:
        # lazy load configured templates
        mod = importlib.import_module("sovereign.configuration")
        templates = mod.XDS_TEMPLATES

        version = self.envoy_version
        selection = "default"
        for v in templates.keys():
            if version.startswith(v):
                selection = v
        selected_version = templates[selection]
        try:
            assert self.resource_type
            return selected_version[self.resource_type]
        except AssertionError:
            raise RuntimeError(
                "DiscoveryRequest has no resource type set, cannot find template"
            )
        except KeyError:
            raise KeyError(
                (
                    f"Unable to get {self.resource_type} for template "
                    f'version "{selection}". Envoy client version: {version}'
                )
            )

    def debug(self):
        return f"version={self.envoy_version}, cluster={self.node.cluster}, resource={self.resource_type}, names={self.resources}"

    def __str__(self) -> str:
        return f"DiscoveryRequest({self.debug()})"


class DiscoveryResponse(BaseModel):
    version_info: str = Field(
        ..., title="The version of the configuration in the response"
    )
    resources: list[Any] = Field(..., title="The requested configuration resources")


class ProcessedTemplate(BaseModel):
    resources: list[dict[str, Any]]
    metadata: list[str] = Field(default_factory=list, exclude=True)

    @computed_field  # type: ignore[prop-decorator]
    @cached_property
    def version_info(self) -> str:
        return compute_hash(self.resources)


class RegisterClientRequest(BaseModel):
    request: DiscoveryRequest
