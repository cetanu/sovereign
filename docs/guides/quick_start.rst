.. _quick_start:

Quick Start
===========
This guide should allow you to get started with a contrived example
of how you would deploy Sovereign.

How do I install it?
--------------------
The package can be installed via pip

.. code-block:: none

   pip install sovereign

How do I run it?
----------------
The following shows an example Dockerfile that you might use to run the server.
You could emulate the same commands used to run it on something that isn't a container, also.

To run the server, configuration must be supplied, and then the
server can execute ``sovereign`` which will start a hypercorn server (an ASGI server).

.. code-block:: dockerfile

   FROM python:3.7

   RUN apt-get update && apt-get -y upgrade

   WORKDIR /proj
   ADD config.yaml /proj/config.yaml
   ADD xds_templates /proj/templates
   RUN pip install sovereign

   EXPOSE 8080
   CMD sovereign

Basic configuration
-------------------
Sovereign requires only a few things to get going:

- Template locations
- Sources (raw data that will generate the templates)
- (optional) Modifications to apply to Sources (using python)

A minimal example of a project structure might look like this:

.. code-block:: none

    /srv/sovereign
      ├── config.yaml
      └── templates
          ├── clusters.yaml
          ├── endpoints.yaml
          ├── listeners.yaml
          └── routes.yaml

For sovereign to load ``config.yaml``, it must be passed in as an environment variable.
For example: ``SOVEREIGN_CONFIG=file:///srv/sovereign/config.yaml``

Example content of the configuration file:

.. code-block:: yaml
    :linenos:

    # /srv/sovereign/config.yaml

    templates:
      1.9.0:
        routes:    file+jinja://templates/routes.yaml
        clusters:  file+jinja://templates/clusters.yaml
        listeners: file+jinja://templates/listeners.yaml
        endpoints: file+jinja://templates/endpoints.yaml

    sources:
      - type: inline
        config:
          instances:
            - name: google-proxy
              service_clusters:
                - "*"
              endpoints:
                - address: google.com.au
                  region: ap-southeast-2
                  port: 443
                - address: google.com
                  region: us-west-1
                  port: 443

templates
  references the location of the templates to use, with the version 1.9.0 to
  indicate that they should only be served to Envoys with that version.

sources
  The sources contains an inline Source, with a little snippet that will
  proxy traffic to Google.

  The structure of the snippet is irrelevant - it can be anything you want -
  as long as your templates are written to handle it.

  .. note::

     The snippet contains a key, ``service_clusters``, with a value of ``"*"``
     - this means it will match all Envoy discovery requests.

     You can control which configuration is provided to Envoys by setting the
     service cluster on your proxies, and adding a list of ``service_clusters`` to your Source data.

     Envoy service cluster can be configured via the `--service-cluster`_ flag

.. _--service-cluster: https://www.envoyproxy.io/docs/envoy/latest/operations/cli#cmdoption-service-cluster