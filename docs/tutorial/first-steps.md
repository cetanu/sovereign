# First Steps

The first things you'll need to do in order to run sovereign are:

* Add 'source(s)'
* Add templates

Start by creating a YAML configuration file

Example:

```yaml
---
sources: []
templates: {}
```

## Adding a source

A source describes the location of the data that will be used to create dynamic envoy configuration.

Without some kind of dynamic source, there's almost no point in using Sovereign as you could accomplish 
what you need using a simple file-based configuration with envoy.
Sovereign is designed to be the broker between a dataset that changes periodically, and envoy configuration.4+

For this example we will use an `inline` source, since it's harder to demonstrate using a file/http source in documentation.

```yaml
---
sources: 
  - type: inline
    config:
      instances:
        # This data can have any structure, 
        # as long as it is a list of key:value mappings
        - name: instance01
          address: 10.0.0.50
          group: A

templates: {}
```

Although you can add multiple sources, for an `inline` source it is somewhat redundant.  
Here is an example anyhow:

```yaml
---
sources: 
  - type: inline
    config:
      instances:
        - name: instance01
          address: 10.0.0.50
          group: A
  - type: inline
    config:
      instances:
        - name: instance01
          address: 10.100.24.10
          group: B

templates: {}
```

When Sovereign starts up, it will read this configuration, and store the instances from all sources in memory.  
They'll look something like this:

```json
[
  {
    "name": "instance01",
    "address": "10.0.0.50",
    "group": "A"
  },
  {
    "name": "instance01",
    "address": "10.100.24.10",
    "group": "B"
  }
]
```

Notice how they're in the same list but they were configured as two separate sources.  
Instances from all sources are placed together.

When generating configuration from templates, a variable `instances` is available that lets you access the instances
so that you can fill out the envoy configuration dynamically.

## Adding templates

A template must be configured for each discovery type that you want to provide from your sovereign server.

As of this writing, the discovery types supported are:

* CDS: Cluster Discovery Service
* LDS: Listener Discovery Service
* RDS: Route Discovery Service
* SRDS: Scoped-Routes Discovery Service
* SDS: Secret Discovery Service

And I'm sure there are more. We don't need to list them all because Sovereign supports them all by default, as long as they don't require gRPC.

Given the above inline sources that we have configured, it makes sense to create a template for clusters to represent the data as clusters:

```yaml
resources:
{% for instance in instances %}
- '@type': type.googleapis.com/envoy.api.v2.Cluster
  name: {{ instance['name'] }}
  connect_timeout: 0.25s
  type: STATIC
  load_assignment:
    cluster_name: {{ instance['name'] }}
    endpoints:
      - lb_endpoints:
          - endpoint:
              address:
                socket_address:
                  address: {{ instance['address'] }}
                  port_value: 80
{% endfor %}
```
