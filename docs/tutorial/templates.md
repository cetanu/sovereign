# Templates

## Discovery Types

A template must be configured for each discovery type that you want to provide from your sovereign server.

As of this writing, the discovery types supported are:

* CDS: Cluster Discovery Service
* LDS: Listener Discovery Service
* RDS: Route Discovery Service
* SRDS: Scoped-Routes Discovery Service
* SDS: Secret Discovery Service

And I'm sure there are more. We don't need to list them all because Sovereign supports them all by default, as long as they don't require gRPC.

## Writing a template

Given the inline sources that we configured in the [last section](/tutorial/sources/), it makes sense to create a template for clusters to represent the data as clusters:

### YAML + Jinja2 example

To get started, it may sometimes help to get an example configuration file from the [Envoy examples](https://github.com/envoyproxy/envoy/tree/master/examples),
and to replace bits of the example with the template syntax.

```yaml
resources:
{% for cluster in clusters %}
- '@type': type.googleapis.com/envoy.api.v2.Cluster
  name: {{ cluster['name'] }}
  connect_timeout: 0.25s
  type: STATIC
  load_assignment:
    cluster_name: {{ cluster['name'] }}
    endpoints:
      - lb_endpoints:
          - endpoint:
              address:
                socket_address:
                  address: {{ cluster['address'] }}
                  port_value: 80
{% endfor %}
```

!!! info

    * Documentation for [YAML](https://yaml.org/spec/1.2/spec.html)
    * Documentation for [Jinja2](https://jinja.palletsprojects.com/en/2.11.x/)

### Python example

For better performance, it's recommended to use Python to describe the templating logic.

The below is an equivalent of the above YAML+Jinja2 example.

```python
def endpoint(address):
    """
    You can write any Python code you like
    to support generating the template
    """
    return {'endpoint': {
                'address': {
                    'socket_address': {
                        'address': address,
                        'port_value': 80}}}}

def call(clusters, discovery_request, **kwargs):
    """
    This function must be defined
    """
    for cluster in clusters:
        # Every yielded item is considered one resource
        # You can also return a list, which will be considered all resources.
        yield {
            '@type': 'type.googleapis.com/envoy.api.v2.Cluster',
            'name': cluster['name'],
            'connect_timeout': '0.25s',
            'type': 'STATIC',
            'load_assignment': {
                'endpoints': [{
                    'lb_endpoints': [
                        endpoint(cluster['address'])
                    ]
                }]
            }
        }
```

Once you've written your first template, you can repeat this process for all other discovery types that you wish to support.

!!! tip

    If you haven't by now, then you should at least read up on the [Envoy API](https://www.envoyproxy.io/docs/envoy/latest/api/api)
    to see exactly what can be configured.  
    I thoroughly recommend keeping this bookmarked.
    
    I also really recommend becoming familiar with the location of each resource type such as 
    [Clusters](https://www.envoyproxy.io/docs/envoy/latest/api-v2/api/v2/cluster.proto#cluster),
    [Listeners](https://www.envoyproxy.io/docs/envoy/latest/api-v2/api/v2/listener.proto#listener),
    [Routes](https://www.envoyproxy.io/docs/envoy/latest/api-v2/api/v2/route.proto#routeconfiguration),
    and filters such as the [Http Connection Manager](https://www.envoyproxy.io/docs/envoy/latest/api-v2/config/filter/network/http_connection_manager/v2/http_connection_manager.proto).

    This will help you immensely when writing templates, and also when considering what data you can include in your Sources.

## Configuring Sovereign with the Templates

Once you have finalized the contents of all your templates, they can be added to Sovereign via it's main configuration file that we created in the previous section:

If you used the Python example above to create your templates, your config might look similar to the following:
```yaml
templates:
  default:
    clusters: python://templates/default/clusters.py
```

Otherwise, if you went with YAML+Jinja2, it may look like:

```yaml
templates:
  default:
    clusters: file+jinja2://templates/default/clusters.j2.yaml
```

!!! note
    
    The scheme used for the template path is generally as follows:
    
    `<type>+<serialization>://<path>`
    
    TODO add link to config loader doco

### Templates for specific versions of Envoy

In the previous configuration examples you'll notice a key called `default`.  
This means that if the Envoy version does not match a specifically configured version, Sovereign will 
use the `default` templates to generate configuration for the Node.

If your fleet of Envoys contains multiple different versions, and the same template wouldn't work across all of them
due to backward compatibility issues, you can configure templates for each version of Envoy that you need to support

!!! example

    ```yaml
    templates:      
      # Versions 1.13.0, 1.13.1
      1.13.1: &v13
        clusters: file+jinja2://templates/v13/clusters.j2.yaml
      1.13.0: *v13
      
      # Versions 1.12.0, 1.12.1, 1.12.2
      1.12.2: &v12
        clusters: file+jinja2://templates/v12/clusters.j2.yaml
      1.12.1: *v12
      1.12.0: *v12
      
      # Everything that doesn't match will use this
      default:
        clusters: file+jinja2://templates/default/clusters.j2.yaml
    ```

!!! tip

    The above example uses [YAML anchors](https://confluence.atlassian.com/bitbucket/yaml-anchors-960154027.html) 
    to avoid needing to type the same path for all patch releases of an Envoy version.
