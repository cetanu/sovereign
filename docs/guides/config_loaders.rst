.. _config_loaders:

Configuration Loaders
---------------------

Loaders
''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''
.. code-block:: none

  - file    : files on-disk
  - pkgdata : python package data
  - http    : plaintext HTTP
  - https   : HTTP over TLS
  - env     : environment variable
  - module  : python module
  - s3      : AWS S3 bucket


Serializers
''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''
.. code-block:: none

  - yaml **DEFAULT**
  - json
  - ujson
  - jinja


Scheme
''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''
.. code-block:: none

   <LOADER>[+SERIALIZER]://<PATH>[,<LOADER>[+SERIALIZER]://<PATH>,...]


Examples
''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''

Single file
  .. code-block:: none

       file:///etc/sovereign.yaml

Multiple files (comma separated)
  .. code-block:: none

       file:///etc/sovereign/common.yaml,file:///etc/sovereign/dev.yaml

HTTP Source
  .. code-block:: none

       http://config.myserver.com/environments/dev.yaml

Mixture of serializers
  .. code-block:: none

       http+json://config.myserver.com/environments/dev.json
       http+jinja://config.myserver.com/environments/dev.j2
       http+yaml://config.myserver.com/environments/dev.yaml
       s3+json://my-bucket-name/file.json
