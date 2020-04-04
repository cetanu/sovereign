# Configuration Options

Sovereign accepts a YAML/JSON configuration file, specified in the environment variable ``SOVEREIGN_CONFIG``.  
Example: ``SOVEREIGN_CONFIG=file:///etc/sovereign.yaml``

## Description of each setting

### `sources`
A list of [Sources](/terminology/#sources) that Sovereign should use to obtain [Instances](/terminology/#instances).

!!! example

    ```yaml
    sources:
      # Clusters from a local file
      - type: file
        scope: clusters
        config:
          path: http+yaml:///etc/envoy/static_clusters.yaml
      # Listeners from an etcd cluster
      - type: file
        scope: listeners
        config:
          path: http+json://etcd.internal:8081/v2/keys/envoy_listeners
      # Other resources from an S3 bucket
      - type: file
        scope: default
        config:
          path: s3+json://my-bucket-name:envoy_data.json
      # Inline routes provided at deployment time
      - type: inline
        scope: routes
        config:
          instances:
            - name: virtualhost_custom_01
              domains: ['*.custom.tld']
              routes:
                - match:
                    prefix: /
                  redirect:
                    host_redirect: somewhere-else.tld
                    path_redirect: /docs
    ```

### `sources_refresh_rate`
  How often (in seconds) Sovereign should refresh all sources. Defaults to 30.

### `source_match_key`
  What key to look for within sources when considering which data should be supplied to particular Envoy proxies.

### `node_match_key`
  What key to look for within the discovery request of an Envoy node, to see which source data it should be supplied with.

### `templates`
  A mapping of version:template_paths to use for discovery requests to sovereign.
  This mapping is flexible when it comes to versions and which templates you intend to use (you don't have to implement
  all of them).

### `template_context`
  A mapping of variable names and loadable paths to make available in templates. A 'loadable path' means that it can
  be evaluated by :ref:`config_loaders`.

refresh_context
  Whether or not to continually reload template context. Default is False.

context_refresh_rate
  How often (in seconds) Sovereign should reload template context. Defaults to 3600.

debug_enabled
  Enable tracebacks and extra detail in certain HTTP error responses.

environment
  An environment string mainly used for logging purposes.

sentry_dsn
  If Sovereign has been installed with Sentry (via ``pip install sovereign[sentry]``), the DSN to send Sentry events to.

auth_enabled
  Controls whether or not Sovereign will reject XDS requests that do not contain auth. Default is false.

  For information on how to enable and supply authentication in XDS requests, see :ref:`Authentication`

auth_passwords
  A list of strings that are considered valid for authentication. When Sovereign receives a
  request from an Envoy proxy, it checks for an ``auth`` field in the node metadata.
  Sovereign attempts to decrypt the field, and checks if it is in this list of strings.

  It is recommended to set this option via the environment variable ``SOVEREIGN_AUTH_PASSWORDS``.

.. danger::
   These passwords allow a person to authenticate to Sovereign and download configuration in plaintext.

encryption_key
  The Fernet key that Sovereign will use to encrypt/decrypt data.

  It is recommended to set this option via the environment variable ``SOVEREIGN_ENCRYPTION_KEY``.

.. danger::
   This key can be used to decrypt any data that has been encrypted by it and then stored, for example in version control.

statsd
  enabled
    Whether or not to emit statsd metrics

  host
    Where to emit statsd metrics

  port
    Port to use when emitting metrics to above host

  tags
    A key:value map of <tag name>: <tag value>
    The value can be preceded by a scheme that allows extended config loading.

    Example:

    .. code-block:: yaml

       statsd:
         tags:
           environment: 'env://SERVICE_ENVIRONMENT'

  namespace
    Suffix for all emitted metrics. Default is ``sovereign``
    See :ref:`Metrics` for a list of metrics emitted.

dns_hard_fail
  When set to True, Sovereign will raise a HTTP exception for any DNS resolution failures that occur when using
  the  ``sovereign.utils.eds:locality_lb_endpoints`` utility.
  If False, it will return the supplied DNS name instead of IP addresses. This may cause Envoy to fail to load the configuration.
  Default is False.

enable_access_logs
  Whether or not to emit HTTP request logs for discovery requests and other endpoints. Logs are JSON formatted.
  Defualt is True

!!! example

    ```yaml
    sources:
      - type: <type>
        scope: 'default'
        config: {}
    
    sources_refresh_rate: 30
    source_match_key: service_clusters
    node_match_key: cluster
    
    templates:
      default:
        clusters: file+jinja2://templates/default/clusters.yaml
        routes: file+jinja2://templates/default/routes.yaml
      1.12.0:
        clusters: file+jinja2://templates/1.12.x/clusters.yaml
        routes: file+jinja2://templates/1.12.x/routes.yaml
      1.13.0:
        clusters: file+jinja2://templates/1.13.x/clusters.yaml
        routes: file+jinja2://templates/1.13.x/routes.yaml
    
    template_context:
      region: env://DEPLOY_REGION
      environment: env://DEPLOY_ENV
      ip_acls: s3://bucket-name:ips.json
    
    refresh_context: no
    context_refresh_rate: 0
    
    debug_enabled: no
    environment: production
    
    sentry_dsn: sentry://blahfoobar
    
    encryption_key: you_should_also_use_environment_variables_for_this!
    auth_enabled: yes
    auth_passwords:
      - VerySecretPassword1!
      - you_should_use_environment_variables_for_this!
    
    statsd:
      enabled: yes
      host: statsd-sink.internal
      port: 8125
      tags:
        region: env://DEPLOY_REGION
        environment: env://DEPLOY_ENV
        hostname: env://HOST
      namespace: sovereign
    
    dns_hard_fail: no
    
    enable_access_logs: yes
    ```

Environment Variables
---------------------

!!! info
    All of the following variables should be prefixed with `SOVEREIGN_`.  
    For example, `HOST` is `SOVEREIGN_HOST`

Environment Variable           | Default           | Description
------------------------------ | ----------------- | ----------------------------
CONFIG               | None              |  Where sovereign should look for it's configuration
HOST                 | 0.0.0.0           |  What address the server will listen on
PORT                 | 8080              |  What port the server will listen on
DEBUG                | False             |  Controls whether the server will log debug messages and tracebacks
ENVIRONMENT_TYPE     | local             |  A label that indicates what environment the server is running in
AUTH_ENABLED         | False             |  Controls whether Sovereign will check node metadata for an encrypted authentication string
AUTH_PASSWORDS       | None              |  A list of passwords that Sovereign will consider valid for decrypted authentication strings
ENCRYPTION_KEY       | None              |  A Fernet key for asymmetric encryption/decryption
NOCHANGE_RESPONSE    | 304               |  What HTTP status should Sovereign return when it detects that the requesting node's config is up-to-date
SOURCE_MATCH_KEY     | service_clusters  |  What value in Source data should sovereign look for when matching nodes
NODE_MATCH_KEY       | cluster           |  What value in the Node Discovery Request should sovereign look for when matching nodes
REFRESH_CONTEXT      | False             |  Whether or not to continually reload template context
CONTEXT_REFRESH_RATE | 3600              |  How often (in seconds) Sovereign should reload template context
SOURCES_REFRESH_RATE | 30                |  How often (in seconds) Sovereign should reload sources (Cannot be disabled)
ENABLE_ACCESS_LOGS   | True              |  Whether or not to emit HTTP request logs for discovery requests
KEEPALIVE            | 5                 |  How long the server should hold connections open for clients before closing
SENTRY_DSN           | None              |  An optional Sentry DSN to send exceptions to
