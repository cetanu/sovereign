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
from sovereign.decorators import memoize


class File(Source):
    def __init__(self, *args, **kwargs):
        super(File, self).__init__(*args, **kwargs)
        for arg in args:
            try:
                self.path = arg['path']
                self.timeout = arg.get('cache_timeout', 30)
                self.jitter = arg.get('cache_jitter', 0)
                break
            except KeyError:
                pass
        else:
            raise KeyError('File source needs to specify "path" within config')

        @memoize(timeout=self.timeout, jitter=self.jitter)
        def _file_source_get(path):
            return load(path)

        self._file_source_get = _file_source_get

    def get(self):
        """
        Uses the file config loader to load the given path
        """
        return self._file_source_get(self.path)

    def __repr__(self):
        return f'{self.__class__.__name__}(path="{self.path}")'
