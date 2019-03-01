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
You can install Sovereign on any machine, but for this example
we're going to create a small Dockerfile that creates a server
for us.

.. code-block:: dockerfile

   FROM python:3.7

   RUN apt-get update && apt-get -y upgrade
   RUN pip install sovereign

   EXPOSE 8080
   CMD sovereign

Project structure
^^^^^^^^^^^^^^^^^
For the purposes of this tutorial I'm going to use the following directory
and files to supply configuration to Sovereign

.. code-block:: none

    /srv/sovereign
      ├── config.yaml
      └── templates
          ├── clusters.yaml
          ├── endpoints.yaml
          ├── listeners.yaml
          └── routes.yaml

Add sources
-----------
Sovereign continually polls configured sources so that it can update configuration in real-time.

The simplest way to add config to sovereign is by adding an inline source.
The disadvantage of an inline source is that you must reload the server if you need to make changes to it.

Example:

.. code-block:: yaml
   :linenos:

   # /srv/sovereign/config.yaml
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

   # /srv/sovereign/config.yaml
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

Using the above example, we could write a clusters template like so:

.. code-block:: jinja
   :linenos:

   # /srv/sovereign/templates/clusters.yaml
   version_info: '{{ version|default(0) }}'
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

The value for ``version_info`` on line 2 will be filled in by a version hash based on the rendered config automatically.

The rest of the file contains ``resources`` which creates envoy cluster configuration based on the inline source from the previous section.

On line 5, a variable named ``endpoints`` is being created using a utility provided by Sovereign.

Once fully rendered using the above inline source, this template will look like the below:

.. code-block:: yaml
   :linenos:

    # /srv/sovereign/templates/clusters.yaml
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
                zone: us-east-1
              lb_endpoints:
                - endpoint:
                    address:
                      socket_address:
                        address: google.com
                        port_value: 443

.. note::

   Lines 10:19 contain the output from the ``eds.locality_lb_endpoints`` utility

Once you've defined a template for every discovery type that you intend to use, you
can add them to the Sovereign config file, like so:

.. code-block:: yaml
   :linenos:
   :emphasize-lines: 13-18

   # /srv/sovereign/config.yaml
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
       routes:    file+jinja:///srv/sovereign/templates/routes.yaml
       clusters:  file+jinja:///srv/sovereign/templates/clusters.yaml
       listeners: file+jinja:///srv/sovereign/templates/listeners.yaml
       endpoints: file+jinja:///srv/sovereign/templates/endpoints.yaml

.. note::

   The key ``default`` on line 14 indicates that these templates will be used in the case that Sovereign
   cannot determine the version of an Envoy client, or cannot match the version with the configured templates.

   This separation is intended to make migrating to newer versions of Envoy easier, as you can define two different
   sets of templates, for example one set for Envoy 1.8.0, and another for 1.9.0.

   Example:

   .. code-block:: yaml

      templates:
        1.8.0: &default_version
          routes:    file+jinja:///srv/sovereign/templates/v1.8.0/routes.yaml
          clusters:  file+jinja:///srv/sovereign/templates/v1.8.0/clusters.yaml
          listeners: file+jinja:///srv/sovereign/templates/v1.8.0/listeners.yaml
          endpoints: file+jinja:///srv/sovereign/templates/v1.8.0/endpoints.yaml
        1.9.0:
          routes:    file+jinja:///srv/sovereign/templates/v1.9.0/routes.yaml
          clusters:  file+jinja:///srv/sovereign/templates/v1.9.0/clusters.yaml
          listeners: file+jinja:///srv/sovereign/templates/v1.9.0/listeners.yaml
          endpoints: file+jinja:///srv/sovereign/templates/v1.9.0/endpoints.yaml
        default: *default_version

Add configuration to Sovereign
------------------------------
For sovereign to load the config file, it must be passed in as an environment variable.
For example: ``SOVEREIGN_CONFIG=file:///srv/sovereign/config.yaml``

Connect an Envoy to Sovereign
-----------------------------
todo



.. _--service-cluster: https://www.envoyproxy.io/docs/envoy/latest/operations/cli#cmdoption-service-cluster
.. _snippets: https://bitbucket.org/snippets/vsyrakis/ae9LEx/sovereign-configuration-examples
