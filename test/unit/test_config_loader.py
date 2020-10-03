import os
import yaml
import pytest

from starlette.exceptions import HTTPException
from sovereign.config_loader import load, is_parseable
from sovereign.discovery import deserialize_config


@pytest.mark.parametrize(
    'path,expected',
    [
        pytest.param('env://BLAH', True, id='env://BLAH'),
        pytest.param('module://json', True, id='module://json'),
        pytest.param('env:/foo', False, id='env:/foo'),
        pytest.param('thing:/foo', False, id='thing:/foo'),
        pytest.param('hello world', False, id='hello world'),
    ]
)
def test_is_parseable(path, expected):
    assert is_parseable(path) == expected


def test_loading_a_file_over_http():
    data = load(
        'https://bitbucket.org'
        '/!api/2.0/snippets/vsyrakis/Ee9yjo/'
        '54ae1495ab113cc669623e538691106c7de313c9/files/controlplane_test.yaml'
    )
    expected = {
        'sources': [{
            'config': {
                'brokers': ['https://google.com/']},
            'type': 'service_broker'
        }]}
    assert data == expected


def test_loading_a_file_over_http_with_json():
    data = load(
        'https+json://bitbucket.org'
        '/!api/2.0/snippets/vsyrakis/qebL6z/'
        '52450800bf05434831f9f702aedaeca0a1b42122/files/controlplane_test.json'
    )
    expected = {
        'sources': [{
            'config': {},
            'type': 'service_broker'
        }]}
    assert data == expected


def test_loading_a_file():
    # --- setup
    config = yaml.safe_load('''
    sources:
      - type: service_broker
        config:
          brokers:
            - https://hello
    ''')
    with open('test_file.yaml', 'w+') as f:
        yaml.dump(config, f)
    # --- load
    data = load(
        'file://./test_file.yaml'
    )
    # --- cleanup
    os.remove('test_file.yaml')
    # --- test
    expected = {
        'sources': [{
            'config': {
                'brokers': ['https://hello']
            },
            'type': 'service_broker'
        }]}
    assert data == expected


def test_config_discovery_malformed_yaml():
    # --- setup
    config = '''
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
    '''

    with pytest.raises(HTTPException):
        deserialize_config(config)


def test_loading_environment_variable():
    data = load('env://CONFIG_LOADER_TEST')
    assert data == {'hello': 'world'}


def test_loading_environment_variable_with_yaml():
    data = load('env+yaml://CONFIG_LOADER_TEST')
    assert data == {'hello': 'world'}


def test_loading_environment_variable_with_json():
    data = load('env+json://CONFIG_LOADER_TEST')
    assert data == {'hello': 'world'}


def test_loading_a_non_parseable_line_returns_a_string():
    data = load('helloworld')
    assert data == 'helloworld'


def test_loading_python_packaged_resources():
    data = load('pkgdata+string://sovereign:static/style.css')
    assert 'font-family:' in data
