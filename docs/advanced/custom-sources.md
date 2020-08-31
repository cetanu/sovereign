# Adding a custom Source

The sources built-in to Sovereign are quite limited, and not all data can be retrieved from a file or from a simple HTTP API.

Sovereign was built to be extended for this reason. Sources can be added by writing a Python module and adding it to a list of entry points that will be loaded when Sovereign starts.


# *Tutorial*: A DNS Service-Discovery Source

In this tutorial we'll go through the steps required to create a Source that
will resolve SRV records using DNS and create Instances based on the results.

### Create a Python module

First, create an empty Python module.

For this example the following folder structure will be used:

```text
├───my_custom_source
│   ├───__init__.py   # <- This file is left empty
│   └───service_discovery.py
└───setup.py
```

### Add a Source to the module

Sovereign provides a Source class which has some methods that must be implemented.  

```python
# my_custom_source/service_discovery.py
from dns.resolver import Resolver
from sovereign.sources.lib import Source
from sovereign.schemas import Instances


class ServiceDiscovery(Source):
    """
    Finds clusters using SRV records
    """

    # If the init needs to be overwritten, it should start as follows
    def __init__(self, config, scope='default'):
        super(ServiceDiscovery, self).__init__(config, scope)
        # -- Start of custom init
        if scope not in ('clusters', 'endpoints'):
            raise ValueError('This source is only supported for clusters/endpoints')

        self.resolver = Resolver()
        configured_resolvers = config.get('resolvers', [])
        if configured_resolvers:
            self.resolver.nameservers = configured_resolvers
        else:
            self.logger.msg('Using resolvers from /etc/resolv.conf')

    def get(self) -> Instances:
       for srv in self.config.get('srv_records', []):
           query = self.resolver.resolve(srv, rdtype='SRV')
           instance = {
               'name': srv,
               'hosts': []
           }
           for answer in query.response.answer:
               *_, priority, weight, port, target = answer.to_text().split()
               instance['hosts'].append({
                   'address': target,
                   'port': port,
                   'weight': weight,
                   'priority': priority,
               })
           yield instance

```

### Write a setuptools script

The following script adds your Python module to the list of sources, which
Sovereign checks at runtime:

```python
from setuptools import setup, find_packages

setup(
    name='my_custom_source',
    packages=find_packages(),
    entry_points={
        "sovereign.sources": [
            "service_discovery = my_custom_source.service_discovery:ServiceDiscovery",
        ]
    }
)
```

This will install the above Python module into an entry point named `sovereign.sources`,  
with a name of `service_discovery`

### Install the Python module in the same place that you installed Sovereign

You'll need to run the above setup script wherever you've installed Sovereign, using `pip install sovereign` or similar.

Simply run `python setup.py install` and you should see output similar to the following:


```bash hl_lines="42"
$ python setup.py install
running install
running bdist_egg
running egg_info
creating my_custom_source.egg-info
writing my_custom_source.egg-info/PKG-INFO
writing dependency_links to my_custom_source.egg-info/dependency_links.txt
writing entry points to my_custom_source.egg-info/entry_points.txt
writing top-level names to my_custom_source.egg-info/top_level.txt
writing manifest file 'my_custom_source.egg-info/SOURCES.txt'
reading manifest file 'my_custom_source.egg-info/SOURCES.txt'
writing manifest file 'my_custom_source.egg-info/SOURCES.txt'
installing library code to build/bdist.macosx-10.9-x86_64/egg
running install_lib
running build_py
creating build
creating build/lib
creating build/lib/my_custom_source
copying my_custom_source/__init__.py -> build/lib/my_custom_source
copying my_custom_source/service_discovery.py -> build/lib/my_custom_source
creating build/bdist.macosx-10.9-x86_64
creating build/bdist.macosx-10.9-x86_64/egg
creating build/bdist.macosx-10.9-x86_64/egg/my_custom_source
copying build/lib/my_custom_source/__init__.py -> build/bdist.macosx-10.9-x86_64/egg/my_custom_source
copying build/lib/my_custom_source/service_discovery.py -> build/bdist.macosx-10.9-x86_64/egg/my_custom_source
byte-compiling build/bdist.macosx-10.9-x86_64/egg/my_custom_source/__init__.py to __init__.cpython-38.pyc
byte-compiling build/bdist.macosx-10.9-x86_64/egg/my_custom_source/service_discovery.py to service_discovery.cpython-38.pyc
creating build/bdist.macosx-10.9-x86_64/egg/EGG-INFO
copying my_custom_source.egg-info/PKG-INFO -> build/bdist.macosx-10.9-x86_64/egg/EGG-INFO
copying my_custom_source.egg-info/SOURCES.txt -> build/bdist.macosx-10.9-x86_64/egg/EGG-INFO
copying my_custom_source.egg-info/dependency_links.txt -> build/bdist.macosx-10.9-x86_64/egg/EGG-INFO
copying my_custom_source.egg-info/entry_points.txt -> build/bdist.macosx-10.9-x86_64/egg/EGG-INFO
copying my_custom_source.egg-info/top_level.txt -> build/bdist.macosx-10.9-x86_64/egg/EGG-INFO
zip_safe flag not set; analyzing archive contents...
creating dist
creating 'dist/my_custom_source-0.0.0-py3.8.egg' and adding 'build/bdist.macosx-10.9-x86_64/egg' to it
removing 'build/bdist.macosx-10.9-x86_64/egg' (and everything under it)
Processing my_custom_source-0.0.0-py3.8.egg
Copying my_custom_source-0.0.0-py3.8.egg to ....../lib/python3.8/site-packages
Adding my-custom-source 0.0.0 to easy-install.pth file

Installed ....../lib/python3.8/site-packages/my_custom_source-0.0.0-py3.8.egg
Processing dependencies for my-custom-source==0.0.0
```

### Configuring Sovereign to use the Source

Similar to how you would use a file/inline source, add it to the list of sources with the type, scope, and config. Example:

```yaml
sources:
  - type: service_discovery
    scope: clusters
    config:
      srv_records:
        # - '_service._proto.domain.tld.'
        - '_imaps._tcp.gmail.com.'  # Real example
```

The above example config should result in something like the following being added to the list of Instances:

```json
{
  "name": "_imaps._tcp.gmail.com.", 
  "hosts": [{
    "address": "imap.gmail.com.",
    "port": "993", 
    "weight": "0", 
    "priority": "5"
  }]
}
```

This data could then be used in a template. Let's say for example we have a clusters template that looked like so:

```yaml
resources:
{% for cluster in clusters %}
- name: {{ cluster['name'] }}
  connect_timeout: 0.25s
  type: STRICT_DNS
  load_assignment:
    cluster_name: {{ cluster['name'] }}
    endpoints:
      {% for host in cluster['hosts'] %}
      - priority: {{ host['priority'] }}
        load_balancing_weight: {{ host['weight'] }}
        lb_endpoints:
          - endpoint:
              address:
                socket_address:
                  address: {{ host['address'] }}
                  port_value: {{ host['port'] }}
      {% endfor %}
{% endfor %}
```

### TODO: verification / run the server and look at the clusters

### Recap

* We created a Python module, containing an object that inherits from Source from the Sovereign library
* We added code that does a DNS lookup on SRV records using a 3rd party library and parses the output into instances
* We made a setup script, and installed it to the same machine which has Sovereign installed
* We added the `service_discovery` source to the list of sources, with an example list of SRV records to lookup
* We verified ... TODO
