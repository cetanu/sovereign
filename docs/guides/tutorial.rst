.. _tutorial:

Tutorial
========

Steps
-----

#. `Install Sovereign`_
#. `Add sources`_
#. `Create templates`_
#. `Add configuration to Sovereign`_
#. `Connect an Envoy to Sovereign`_
#. `Confirm the setup works`_


Install Sovereign
-----------------

Project structure
^^^^^^^^^^^^^^^^^
For the purposes of this tutorial I'm going to use the following directory
and files to supply configuration to Sovereign

.. code-block:: none

    /proj/sovereign
      ├── Dockerfile.sovereign
      ├── Dockerfile.envoy
      ├── bootstrap.yaml
      ├── config.yaml
      ├── docker-compose.yml
      └── templates
          ├── clusters.yaml
          ├── endpoints.yaml
          ├── listeners.yaml
          └── routes.yaml

Creating a Dockerfile for Sovereign
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
You can install Sovereign on any machine, but for this tutorial
we're going to create a small Dockerfile that creates a server
for us.

.. code-block:: dockerfile

   # /proj/sovereign/Dockerfile.sovereign

   FROM python:3.7

   RUN apt-get update && apt-get -y upgrade
   RUN pip install sovereign

   ADD templates /etc/sovereign/templates
   ADD config.yaml /etc/sovereign/config.yaml
   ENV SOVEREIGN_CONFIG=file:///etc/sovereign/config.yaml

   EXPOSE 8080
   CMD sovereign


Add sources
-----------
Sovereign continually polls configured sources so that it can update configuration in real-time.

The simplest way to add config to sovereign is by adding an inline source.
The disadvantage of an inline source is that you must reload the server if you need to make changes to it.

Example:

.. code-block:: yaml
   :linenos:

   # /proj/sovereign/config.yaml
   sources:
     - type: inline
       config:
         instances:
           - name: google-proxy
             service_clusters: ['*']
             domains:
               - example.local
             endpoints:
               - address: google.com
                 port: 443
                 region: us-east-1

.. note::

   Envoy can be configured with a service cluster via the `--service-cluster`_ flag.

   You can control which configuration is provided to particular Envoys by setting the
   service cluster, and adding an array of ``service_clusters`` to your Source data.

   Line 7 of the snippet, ``service_clusters: ['*']`` means that this instance will
   match *all* discovery requests.

   Examples of service clusters you might want to set could be development/staging/production.

Configuring a more dynamic source
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
The recommended way to get Sovereign to provide dynamic configuration is to have it poll
a File source (which can be a local file, or a file over HTTPS).

To illustrate how this would work, I've set up two public snippets_ of config on Bitbucket.org.

The configuration that I would supply to Sovereign in order for it to continually check these
sources for changes would be as follows:

.. code-block:: yaml
   :linenos:

   # /proj/sovereign/config.yaml
   sources:
     - type: file
       config:
         path: https+yaml://bitbucket.org/!api/2.0/snippets/vsyrakis/ae9LEx/master/files/service1.yaml
     - type: file
       config:
         path: https+yaml://bitbucket.org/!api/2.0/snippets/vsyrakis/ae9LEx/master/files/service2.yaml

This would result in all of the items from the two configured sources becoming available as ``instances``
within the templates (that you will create in the next section) that render envoy configuration.

If at any point I decided I want to change these snippets, Sovereign would detect the changes and supply
envoy proxies with the new configuration.

Create templates
----------------
Sovereign needs a template for each discovery type that it's going
to be responding with.

How you write your templates depends on the structure of the source data
that you've configured Sovereign with.

Example "clusters" template
^^^^^^^^^^^^^^^^^^^^^^^^^^^

Using the above example, we could write a clusters template like so:

.. code-block:: jinja
   :linenos:

   # /proj/sovereign/templates/clusters.yaml
   resources:
   {% for instance in instances %}
     {% set endpoints = eds.locality_lb_endpoints(instance.endpoints, discovery_request, resolve_dns=False) %}
     - '@type': type.googleapis.com/envoy.api.v2.Cluster
       name: {{ instance.name }}-cluster
       connect_timeout: 5s
       type: strict_dns
       load_assignment:
         cluster_name: {{ instance.name }}-cluster
         endpoints: {{ endpoints|tojson }}
   {% endfor %}

On line 5, a variable named ``endpoints`` is being created using a utility provided by Sovereign.

Once fully rendered using the above inline source, this template will look like the below:

.. code-block:: yaml
   :linenos:

    version_info: '124872349835'
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
                zone: us-east-1
              lb_endpoints:
                - endpoint:
                    address:
                      socket_address:
                        address: google.com
                        port_value: 443

.. note::

   Lines 9:18 contain the output from the ``eds.locality_lb_endpoints`` utility

Example "listeners" template
^^^^^^^^^^^^^^^^^^^^^^^^^^^^
todo: explanation

.. code-block:: jinja
   :linenos:

   # /proj/sovereign/templates/listeners.yaml
   resources:
     - '@type': type.googleapis.com/envoy.api.v2.Listener
       name: http_listener
       address:
         socket_address:
           address: 0.0.0.0
           port_value: 80
           protocol: TCP
       filter_chains:
         - filters:
           - name: envoy.http_connection_manager
             config:
               stat_prefix: backends
               codec_type: AUTO
               access_log:
                 - name: envoy.file_access_log
                   config:
                     path: /dev/stdout
               http_filters:
                 - name: envoy.router
                   config: {}
               route_config:
                 name: example
                 virtual_hosts:
                 {% for instance in instances %}
                 - name: backend
                   domains: {{ instance.domains|tojson }}
                   routes:
                   - match:
                       prefix: /
                     route:
                       cluster: "{{ instance.name }}-cluster"
                 {% endfor %}

.. _adding_templates:

Adding templates to your config
-------------------------------

Once you've defined a template for every discovery type that you intend to use, you
can add them to the Sovereign config file, like so:

.. code-block:: yaml
   :linenos:
   :emphasize-lines: 13-18

   # /proj/sovereign/config.yaml
   sources:
     - type: inline
       config:
         instances:
           - name: google-proxy
             service_clusters: ['*']
             endpoints:
               - address: google.com
                 port: 443
                 region: us-east-1

   templates:
     default:
       clusters:  file+jinja:///etc/sovereign/templates/clusters.yaml
       listeners: file+jinja:///etc/sovereign/templates/listeners.yaml

.. note::

   The key ``default`` on line 14 indicates that these templates will be used in the case that Sovereign
   cannot determine the version of an Envoy client, or cannot match the version with the configured templates.

   This separation is intended to make migrating to newer versions of Envoy easier, as you can define two different
   sets of templates, for example one set for Envoy 1.8.0, and another for 1.9.0.

   Example:

   .. code-block:: yaml

      templates:
        1.8.0: &default_version
          routes:    file+jinja:///proj/sovereign/templates/v1.8.0/routes.yaml
          clusters:  file+jinja:///proj/sovereign/templates/v1.8.0/clusters.yaml
          listeners: file+jinja:///proj/sovereign/templates/v1.8.0/listeners.yaml
          endpoints: file+jinja:///proj/sovereign/templates/v1.8.0/endpoints.yaml
        1.9.0:
          routes:    file+jinja:///proj/sovereign/templates/v1.9.0/routes.yaml
          clusters:  file+jinja:///proj/sovereign/templates/v1.9.0/clusters.yaml
          listeners: file+jinja:///proj/sovereign/templates/v1.9.0/listeners.yaml
          endpoints: file+jinja:///proj/sovereign/templates/v1.9.0/endpoints.yaml
          secrets:   file+jinja:///proj/sovereign/templates/v1.9.0/secrets.yaml
        default: *default_version


Add configuration to Sovereign
------------------------------
For sovereign to load the config file, it must be passed in as an environment variable.
For example: ``SOVEREIGN_CONFIG=file:///etc/sovereign/config.yaml``

Connect an Envoy to Sovereign
-----------------------------
In order to test if Sovereign is correctly rendering configuration and supplying it
to Envoy clients, we're going to use the following Dockerfile to spawn an Envoy container
and connect it to the Sovereign container.

.. code-block:: dockerfile
   :linenos:

   # /proj/sovereign/Dockerfile.envoy

   FROM envoyproxy/envoy:v1.11.1
   EXPOSE 80 443 8080 9901
   ADD bootstrap.yaml /etc/envoy.yaml
   CMD envoy -c /etc/envoy.yaml

You'll notice on line 5 that we add a file named bootstrap.yaml as the config that envoy
will use to boot up.
The contents of the bootstrap configuration should be as follows:

.. code-block:: yaml
   :linenos:

   # /proj/sovereign/bootstrap.yaml

   node:
     id: envoy
     cluster: dev
     metadata:
       ipv4: 127.0.0.1
       auth: <secret key>

   admin:
     access_log_path: /dev/null
     address:
       socket_address:
         address: 0.0.0.0
         port_value: 9901

   dynamic_resources:
     lds_config:
       api_config_source:
         api_type: REST
         cluster_names: [controlplane]
         refresh_delay: 15s
     cds_config:
       api_config_source:
         api_type: REST
         cluster_names: [controlplane]
         refresh_delay: 5s

   static_resources:
     clusters:
     - name: controlplane
       connect_timeout: 5s
       type: STRICT_DNS
       hosts:
       - socket_address:
           address: sovereign
           port_value: 8080

This is a lot of information unless you're intimately familiar with Envoy, so I'll break it down line by line.

* Lines 3-8 contains information about the node itself. You could use this to set a particular name/id, and service cluster.
  This information is presented to sovereign on every discovery request. At the moment sovereign only cares about the
  service cluster, and two fields under metadata, ipv4 and auth, neither of which are required. Auth will be explained later.
* Lines 10-15 expose an admin web UI for envoy on port 9901, which does not log. If you log into the container you can
  run commands against the envoy, which we'll see later.
* Line 17 is the start of the dynamic resources that the envoy proxy will be polling sovereign for.
* Lines 18-22 will cause Envoy to send a POST request to sovereign with a path of ``/v2/discovery:listeners``
  every 15 seconds.
* Lines 23-27 will cause Envoy to send a similar request, but to ``/v2/discovery:clusters`` every 5 seconds.
* Lines 29-37 define a cluster named 'controlplane' that contains the sovereign host (which will be accessed by this name
  within the docker network).

You can include any static configuration that you like in this bootstrap file, but changing it would then require hot-restarting Envoy.

Making the process easier with docker-compose
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
In order to run both sovereign and envoy as containers in a shared network with basic name resolution, we'll use a
docker-compose file to launch the containers.

The compose file should look as follows:

.. code-block:: yaml

   # /proj/sovereign/docker-compose.yml

   version: '2.3'

   services:
     sovereign:
       container_name: sovereign
       build:
         context: .
         dockerfile: Dockerfile.sovereign
       environment:
         SOVEREIGN_HOST: '0.0.0.0'
         SOVEREIGN_PORT: '8080'
         SOVEREIGN_DEBUG: 'yes'
         SOVEREIGN_ENVIRONMENT_TYPE: local
         SOVEREIGN_CONFIG: file:///etc/sovereign/config.yaml
       ports:
         - 80:8080
       expose:
         - 80

     envoy:
       container_name: envoy
       build:
         context: .
         dockerfile: Dockerfile.envoy
       links:
         - sovereign
       expose:
         - 9901


Confirm the setup works
^^^^^^^^^^^^^^^^^^^^^^^
todo: add example of running compose setup


.. _--service-cluster: https://www.envoyproxy.io/docs/envoy/latest/operations/cli#cmdoption-service-cluster
.. _snippets: https://bitbucket.org/snippets/vsyrakis/ae9LEx/sovereign-configuration-examples
