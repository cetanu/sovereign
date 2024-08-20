import os

import boto3
import pytest
import yaml
from moto import mock_s3
from sovereign.dynamic_config import Loadable
from sovereign.dynamic_config.loaders import S3Bucket
from sovereign.dynamic_config.deser import JsonDeserializer, UjsonDeserializer, OrjsonDeserializer
from sovereign.discovery import deserialize_config
from starlette.exceptions import HTTPException


def test_loading_a_file_over_http():
    data = Loadable.from_legacy_fmt(
        "http://http_server:8080/controlplane_test.yaml"
    ).load()
    expected = {
        "sources": [
            {"config": {"brokers": ["https://google.com/"]}, "type": "service_broker"}
        ]
    }
    assert data == expected


def test_loading_a_file_over_http_with_json():
    data = Loadable.from_legacy_fmt(
        "http+json://http_server:8080/controlplane_test.json"
    ).load()
    expected = {"sources": [{"config": {}, "type": "service_broker"}]}
    assert data == expected


def test_loading_a_file():
    # --- setup
    config = yaml.safe_load(
        """
    sources:
      - type: service_broker
        config:
          brokers:
            - https://hello
    """
    )
    with open("test_file.yaml", "w+") as f:
        yaml.dump(config, f)
    # --- load
    data = Loadable.from_legacy_fmt("file://./test_file.yaml").load()
    # --- cleanup
    os.remove("test_file.yaml")
    # --- test
    expected = {
        "sources": [
            {"config": {"brokers": ["https://hello"]}, "type": "service_broker"}
        ]
    }
    assert data == expected


def test_config_discovery_malformed_yaml():
    # --- setup
    config = """
      - name: ssr_cluster
        service_clusters:
            - "*"
        type: ssr-cluster
        endpoints:
            - address: best-cluster
            ports:
                - 443
            status: HEALTHY

      - name: repomigrate
        service_clusters:
          - "*"
        type: http-srv-cluster
        endpoints:
          - address: hgsrv-s01.us-west-2.bb-inf.net
            ports:
              - 8081
            region: us-west-2
          - address:
            ports: hgsrv-s02.us-west-2.bb-inf.net
              - 8081
            region: us-west-2
    """

    with pytest.raises(HTTPException):
        deserialize_config(config)


def test_loading_environment_variable():
    data = Loadable.from_legacy_fmt("env://CONFIG_LOADER_TEST").load()
    assert data == {"hello": "world"}


def test_loading_environment_variable_with_yaml():
    data = Loadable.from_legacy_fmt("env+yaml://CONFIG_LOADER_TEST").load()
    assert data == {"hello": "world"}


def test_loading_environment_variable_with_json():
    data = Loadable.from_legacy_fmt("env+json://CONFIG_LOADER_TEST").load()
    assert data == {"hello": "world"}


@mock_s3
@pytest.mark.parametrize(
    "deserializer",
    [
        JsonDeserializer,
        UjsonDeserializer,
        OrjsonDeserializer,
    ],
)
def test_loading_s3_with_json(deserializer):
    example_data = b'{"hello": "world"}'
    bucket_name = "test_bucket"
    key = "test_key.txt"

    s3_client = boto3.client("s3")
    s3_client.create_bucket(Bucket=bucket_name)
    s3_client.put_object(Body=example_data, Bucket=bucket_name, Key=key)

    data = S3Bucket().load(path=f"{bucket_name}/{key}")
    obj = deserializer().deserialize(data)
    assert obj == {"hello": "world"}


def test_loading_a_non_parseable_line_returns_a_string():
    data = Loadable.from_legacy_fmt("helloworld").load()
    assert data == "helloworld"


def test_loading_python_packaged_resources():
    data = Loadable.from_legacy_fmt(
        "pkgdata+string://sovereign:static/style.css"
    ).load()
    assert "font-family:" in data
