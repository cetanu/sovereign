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

Configuration
^^^^^^^^^^^^^
The main job of the configuration that you will supply to sovereign is to
tell it where to find templates used for Envoy discovery requests, contextual
data that should be available in the template, what modifications should be
performed (via custom modifiers), and where to obtain data from (sources) so
that sovereign can dynamically render configuration for your proxies in real-time.

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

Explanation of the above
  template_context
    utils, eds, crypto
      Loads the templates, eds, and crypto python module from the sovereign utils, respectively.

    certificates
      Loads in a yaml file containing certificates for Envoy to use when providing
      listener configuration.

  templates
    Lists some template files which Sovereign should load, for each discovery type.
    It also specifies the Envoy version that it will render config for. It will not
    render for other versions. This is a feature to help migrations to new Envoy
    versions while maintaining backward compatibility.

See `Configuration`_ for instructions on adding the above type of configuration to
Sovereign.


Templates
^^^^^^^^^
As you might guess by looking above, each template corresponds to a type of
discovery service in Envoy.

The template must eventually render out to a form that Envoy will understand.
You can see large examples at `<insert link to repo templates>`_

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
