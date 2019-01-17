Getting Started
---------------
To begin, you'll need templates and a configuration file.

A minimal example of a project might look like this:

.. code-block:: none

    ├── config.yaml
    └── templates
        ├── clusters.yaml
        ├── endpoints.yaml
        ├── listeners.yaml
        └── routes.yaml

Configuring Sovereign
^^^^^^^^^^^^^^^^^^^^^
The control plane loads configurations from the environment variable ``SOVEREIGN_CONFIG``.

The main job of the configuration that you will supply to sovereign is to
tell it where to find:

- Templates used for Envoy discovery requests
- Contextual data that should be available in the template
- *(Optional)* What modifications should be performed (via custom modifiers)
- Where to obtain instance data from (sources)

A basic configuration may look like:

.. code-block:: yaml

    template_context:
      utils: module://sovereign.utils.templates
      eds: module://sovereign.utils.eds
      crypto: module://sovereign.utils.crypto
      certificates: file://deploy/environments/dev/certificates.yaml

    templates:
      1.9.0:
        routes:    file+jinja://xds_templates/1.9.0/routes.yaml
        clusters:  file+jinja://xds_templates/1.9.0/clusters.yaml
        listeners: file+jinja://xds_templates/1.9.0/listeners.yaml
        endpoints: file+jinja://xds_templates/1.9.0/endpoints.yaml

    sources:
      - type: file
        config:
          path: https://bitbucket.org/!api/2.0/snippets/vsyrakis/ae9LEx/master/files/service1.yaml
      - type: file
        config:
          path: https://bitbucket.org/!api/2.0/snippets/vsyrakis/ae9LEx/master/files/service2.yaml


Explanation of the above
""""""""""""""""""""""""
template_context
  The following variables can be referenced in templates to aid with the generation of config.

  utils, eds, crypto
    Loads the templates, eds, and crypto python module from the sovereign utils, respectively.

  certificates
    Loads in a yaml file containing certificates for Envoy to use when providing
    listener configuration.
    In our example at Atlassian, we store the certificates encrypted, and use the above **crypto**
    variable to decrypt them before providing them to the Envoy clients.

templates
  Lists some template files which Sovereign should load, for each discovery type.
  It also specifies the Envoy version that it will render config for. It will not
  render for other versions. This is a feature to help migrations to new Envoy
  versions while maintaining backward compatibility.

sources
  These sources tell sovereign to download some instance data from the linked bitbucket snippet.
  The instance data will be used to generate configuration later on.
  You can check these examples via the above URLs, which proxy major tech company websites as a very basic example.

See :ref:`config_loaders` for examples on adding the above type of configuration to Sovereign.

.. note::
   The ``SOVEREIGN_CONFIG`` environment variable above is also loaded using config loaders.
   This means that you can load it using any of the available schemes, for example on disk, or via a HTTP endpoint.

Templates
^^^^^^^^^
As you might guess by looking at the above example configuration, each template
corresponds to a type of discovery service in Envoy.

The template must eventually render out to a form that Envoy will understand.
You can see `examples in the sovereign repo <https://bitbucket.org/atlassian/sovereign/src/master/xds_templates>`_

A small cluster snippet might look like:

.. code-block:: yaml

    version_info: 'abcdef1234'
    resources:
      - '@type': type.googleapis.com/envoy.api.v2.Cluster
        name: helloworld-google-proxy-example
        connect_timeout: 5s
        dns_lookup_family: V4_ONLY
        type: strict_dns
        load_assignment:
          cluster_name: google
          endpoints:
            - lb_endpoints:
                - endpoint:
                    address:
                      socket_address:
                        address: google.com.au
                        port_value: 443

.. note::
   Templates are rendered using `Jinja2 <http://jinja.pocoo.org/docs/2.10/>`_

Guidelines for creating templates
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
To begin with, there are a few important variables that are made available via template context:

version
  This is a string that is automatically generated based off the contents
  of the template after it has been fully rendered.

  In general, your templates should start with the following:

  .. code-block:: yaml

     version_info: '{{ version|default(0) }}'

instances
  When sovereign executes all of the sources it has configured, it will place the results
  into this variable.

  So, depending on what you have configured for sources, this is the main variable that
  determines what will be rendered into the template.

An example template based on the example configuration
""""""""""""""""""""""""""""""""""""""""""""""""""""""
This example would run through the following steps before being rendered and given to an Envoy client.

Sovereign more-or-less does the following in order:

#. Reads the configured sources but does not get any instance data
#. Receives a CDS discovery request from an Envoy proxy
#. Gets all sources (i.e. 3 instances from the two bitbucket snippets above)
#. Renders the below template

   #. Begins to loop over the 3 instances
   #. Feeds the 'endpoints' field into :func:`sovereign.utils.eds.locality_lb_endpoints`
   #. Creates a cluster using the endpoints and name, for each instance
   #. Hashes the entire configuration
   #. Inserts the hash into the ``version_info``

#. If the Envoy proxy provided a different ``version_info`` in its request, it returns
   the configuration with a 200 OK, otherwise it returns 304 Not Modified

.. code-block:: jinja

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
