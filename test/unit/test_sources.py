import pytest
from sovereign.sources import match_node, extract_node_key
from sovereign.sources.inline import Inline
from sovereign.sources.file import File


def test_inline_source():
    source = Inline({'instances': ['something']})
    assert source.get() == source.instances
    assert source.get() == ['something']


def test_inline_source_bad_config():
    with pytest.raises(KeyError):
        Inline({'key': 'value'})


def test_file_source():
    source = File({'path': 'file://test/config/config.yaml'})
    assert 'sources' in source.get()


def test_file_source_bad_config():
    with pytest.raises(KeyError):
        File({'abc': 'foo'})


def test_loading_sources_t1(discovery_request, sources):
    expected = {
        'scopes': {
            'listeners': [
                {
                    'name': 'ssh',
                    'port': 22,
                    'tcp': True,
                    'target': 'httpbin-proxy',
                    'service_clusters': ['T1']
                }
            ],
            'default': [
                {
                    'name': 'httpbin-proxy',
                    'service_clusters': ['T1'],
                    'domains': [
                        'example.local'
                    ],
                    'endpoints': [
                        {
                            'address': 'httpbin.org',
                            'port': 443
                        }
                    ],
                },
            ]
        }
    }
    instances = match_node(node_value=extract_node_key(discovery_request.node))
    assert instances.dict() == expected


def test_loading_sources_x1(discovery_request, sources):
    expected = {
        'scopes': {
            'default': [
                {
                    'name': 'google-proxy',
                    'service_clusters': ['X1'],
                    'domains': [
                        'google.local'
                    ],
                    'endpoints': [
                        {
                            'address': 'google.com.au',
                            'port': 443,
                            'region': 'ap-southeast-2'
                        },
                        {
                            'address': 'google.com',
                            'port': 443,
                            'region': 'us-west-1'
                        }
                    ],
                }
            ]
        }
    }
    discovery_request.node.cluster = 'X1'
    instances = match_node(node_value=extract_node_key(discovery_request.node))
    assert instances.dict() == expected


def test_loading_sources_wildcard(discovery_request, sources):
    expected = {
        'scopes': {
            'listeners': [
                {
                    'name': 'ssh',
                    'port': 22,
                    'tcp': True,
                    'target': 'httpbin-proxy',
                    'service_clusters': ['T1']
                }
            ],
            'default': [
                {
                    'name': 'google-proxy',
                    'service_clusters': ['X1'],
                    'domains': [
                        'google.local'
                    ],
                    'endpoints': [
                        {
                            'address': 'google.com.au',
                            'port': 443,
                            'region': 'ap-southeast-2'
                        },
                        {
                            'address': 'google.com',
                            'port': 443,
                            'region': 'us-west-1'
                        }
                    ],
                },
                {
                    'name': 'httpbin-proxy',
                    'service_clusters': ['T1'],
                    'domains': [
                        'example.local'
                    ],
                    'endpoints': [
                        {
                            'address': 'httpbin.org',
                            'port': 443
                        }
                    ],
                }
            ]
        }
    }
    discovery_request.node.cluster = '*'
    instances = match_node(node_value=extract_node_key(discovery_request.node))
    assert instances.dict() == expected
