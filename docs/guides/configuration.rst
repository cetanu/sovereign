Configuration
-------------

The control plane loads configurations from the environment variable
``SOVEREIGN_CONFIG`` which accepts the format:

.. code-block:: none

   <LOADER>[+SERIALIZER]://<PATH>[,<LOADER>[+SERIALIZER]://<PATH>,...]

Available loaders:

  - file    : files on-disk
  - pkgdata : python package data
  - http    : plaintext HTTP
  - https   : HTTP over TLS
  - env     : environment variable
  - module  : python module

Available serializers:

  - yaml **DEFAULT**
  - json
  - jinja

Examples:

.. code-block:: none

   # Single file
     file:///etc/sovereign.yaml

   # Multiple files (comma separated)
     file:///etc/sovereign/common.yaml,file:///etc/sovereign/dev.yaml

   # Other types of sources
     http://config.myserver.com/environments/dev.yaml

   # Other types of formats
     http+json://config.myserver.com/environments/dev.json
     http+jinja://config.myserver.com/environments/dev.j2
     http+yaml://config.myserver.com/environments/dev.yaml
