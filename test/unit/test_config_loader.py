import os
import yaml
from sovereign.config_loader import load


def test_loading_http_spec():
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


def test_loading_http_spec_with_json():
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


def test_loading_file_spec():
    # --- setup
    config = yaml.load('''
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


def test_loading_env():
    data = load('env://HOME')
    assert data == '/root'


def test_loading_env_yaml():
    data = load('env+yaml://HOME')
    assert data == '/root'


def test_loading_env_json():
    data = load('env+json://CONFIG_LOADER_TEST')
    assert data == {'hello': 'world'}
