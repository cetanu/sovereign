"""
File Source
-----------

Example(s) configuration file (YAML):

.. code-block:: yaml

   sources:
     - type: file
       config:
         path: file:///tmp/instances.yaml
     - type: file
       config:
         path: file+json:///tmp/instances.json
     - type: file
       config:
         path: https://mywebsite.com/configuration/instances.yaml
     - type: file
       config:
         path: https+json://mywebsite.com/configuration/instances.json
     - type: file
       config:
         path: https+json://mywebsite.com/configuration/instances.json
     - type: file
       config:
         path: pkgdata://sovereign:config/instances.yaml

Example of what the contents should look like:

.. code-block:: yaml

   - instance_id: <identifier>
     service_clusters:
       - P2
     parameters:
       clusters:
         - name: upstream
           healthchecks:
             - path: /healthcheck
           hosts:
             - address: aws.amazon.com
               port: 443
               region: us-east-1
         vhosts:
         - clusters:
             - name: upstream
           domains:
             - aws.amazon.com
             - amazon.dev.globaledge.internal
           name: vhost
           rewrite: 'yes'
"""
from sovereign.sources.lib import Source
from sovereign.config_loader import load


class File(Source):
    def __init__(self, config, scope='default'):
        super(File, self).__init__(config, scope)
        try:
            self.path = config['path']
        except KeyError:
            raise KeyError('File source needs to specify "path" within config')

    def get(self):
        """
        Uses the file config loader to load the given path
        """
        return load(self.path)
