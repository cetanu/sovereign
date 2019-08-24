.. _quick_start:

Quick Start
===========
This guide should allow you to get started with a contrived example
of how you would deploy Sovereign.

Minimal configuration
---------------------
Sovereign requires only a few things to get going:

- Templates
- Data Sources

An example of a project structure might look like this:

.. code-block:: none

    /proj
      ├── config.yaml
      └── templates
          ├── clusters.yaml
          ├── endpoints.yaml
          ├── listeners.yaml
          └── routes.yaml

For sovereign to load ``config.yaml``, it must be passed in as an environment variable.
For example: ``SOVEREIGN_CONFIG=file:///proj/config.yaml``

Example content of the configuration file:

.. code-block:: yaml
    :linenos:

    # /proj/config.yaml

    templates:
      1.11.1: &default_version
        routes:    file+jinja:///proj/templates/routes.yaml
        clusters:  file+jinja:///proj/templates/clusters.yaml
        listeners: file+jinja:///proj/templates/listeners.yaml
        endpoints: file+jinja:///proj/templates/endpoints.yaml
      default: *default_version

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
  A default version must be specified, in case Sovereign cannot determine the
  version of an envoy proxy.

sources
  The source in the example contains an inline Source, with a snippet that will
  proxy traffic to Google. There are other :ref:`sources` available too.

  The structure of the snippet is irrelevant - it can be anything you want -
  as long as your templates are written to handle it.

  .. note::

     The snippet contains a key, ``service_clusters``, with a value of ``"*"``
     - this means it will match all Envoy discovery requests.

     You can control which configuration is provided to Envoys by setting the
     service cluster on your proxies, and adding a list of ``service_clusters`` to your Source data.

     Envoy service cluster can be configured via the `--service-cluster`_ flag

.. _--service-cluster: https://www.envoyproxy.io/docs/envoy/latest/operations/cli#cmdoption-service-cluster


Templates
^^^^^^^^^
As you might guess by looking at the above example configuration, each template
corresponds to a type of discovery service in Envoy; clusters, endpoints, routes, or listeners.

The template must eventually render out to a schema that Envoy will understand.
You can see `examples in the sovereign repo <https://bitbucket.org/atlassian/sovereign/src/master/templates/default/>`_

Accessing sources in templates
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
All templates have access to a variable named ``instances``.

When sovereign retrieves all of the sources it has configured, it will place the results
into this variable.

So, depending on what you have configured for sources, this is the main variable that
determines what will be rendered into the template.

A template based on the example configuration
"""""""""""""""""""""""""""""""""""""""""""""

.. note::
   Templates are rendered using `Jinja2 <http://jinja.pocoo.org/docs/2.10/>`_

The steps that Sovereign runs through before rendering a template and returning it to an Envoy:

#. Receives a CDS discovery request from an Envoy proxy
#. Retrieves all sources (inline configuration in this example)
#. Calculates the ``version_info`` of the configuration prior to rendering the templates
#. If ``version_info`` of the discovery request is the same as calculated sovereigns returns 304 Not Modified
#. Otherwise, sovereign renders the below template
   #. Begins to loop over the 'google-proxy' instance
   #. Feeds the 'endpoints' field into :func:`sovereign.utils.eds.locality_lb_endpoints`
   #. Creates a cluster using the endpoints and name, for each instance
   #. Inserts the checksum into the ``version_info``
#. Returns 200 OK

.. code-block:: jinja

   resources:
   {% for instance in instances %}
     {% set endpoints = eds.locality_lb_endpoints(instance.endpoints, discovery_request, resolve_dns=False) %}
     - '@type': type.googleapis.com/envoy.api.v2.Cluster
       name: {{ instance.name }}
       connect_timeout: 5s
       type: strict_dns
       load_assignment:
         cluster_name: {{ instance.name }}-cluster
         endpoints: {{ endpoints|tojson }}
   {% endfor %}

Once fully rendered using the above inline source, this template will look like this:

.. code-block:: yaml

    version_info: '6d75b172b2d00c2c50b570fa82a136aa6f9720b54dd2bd836bcdacc5eeb2bec2'
    resources:
      - '@type': type.googleapis.com/envoy.api.v2.Cluster
        name: google-proxy
        connect_timeout: 5s
        type: strict_dns
        load_assignment:
          cluster_name: google-proxy-cluster
          endpoints:
            - priority: 10
              locality:
                zone: ap-southeast-2
              lb_endpoints:
                - endpoint:
                    address:
                      socket_address:
                        address: google.com.au
                        port_value: 443
            - priority: 10
              locality:
                zone: us-west-1
              lb_endpoints:
                - endpoint:
                    address:
                      socket_address:
                        address: google.com
                        port_value: 443

Creating a container
--------------------
The following shows an example Dockerfile that you might use to run the server.
You could emulate the same commands used to run it on something that isn't a container, also.

.. code-block:: dockerfile

   FROM python:3.7

   RUN apt-get update && apt-get -y upgrade

   WORKDIR /proj
   ADD config.yaml /proj/config.yaml
   ADD xds_templates /proj/templates
   RUN pip install sovereign

   ENV SOVEREIGN_CONFIG=file:///proj/config.yaml

   EXPOSE 8080
   CMD sovereign
