.. _config_loaders:

Available Configuration Loaders
-------------------------------


Path scheme
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.. code-block:: none

   <LOADER>[+SERIALIZER]://<PATH>[,<LOADER>[+SERIALIZER]://<PATH>,...]


Available loaders
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.. code-block:: none

  - file    : files on-disk
  - pkgdata : python package data
  - http    : plaintext HTTP
  - https   : HTTP over TLS
  - env     : environment variable
  - module  : python module


Available serializers
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.. code-block:: none

  - yaml **DEFAULT**
  - json
  - jinja


Examples
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.. code-block:: none

Single file
"""""""""""""""""""""""""""""""""""""

.. code-block:: none

     file:///etc/sovereign.yaml

Multiple files (comma separated)
"""""""""""""""""""""""""""""""""""""

.. code-block:: none

     file:///etc/sovereign/common.yaml,file:///etc/sovereign/dev.yaml

Other types of sources
"""""""""""""""""""""""""""""""""""""

.. code-block:: none

     http://config.myserver.com/environments/dev.yaml

Other types of formats
"""""""""""""""""""""""""""""""""""""

.. code-block:: none

     http+json://config.myserver.com/environments/dev.json
     http+jinja://config.myserver.com/environments/dev.j2
     http+yaml://config.myserver.com/environments/dev.yaml
