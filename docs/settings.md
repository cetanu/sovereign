# Configuration Options

By default Sovereign will look for a YAML/JSON configuration file at `/etc/sovereign.yaml`

This can be overridden with the environment variable `SOVEREIGN_CONFIG`

!!! example

    Loading configuration from an alternate location, eg. `/srv/sovereign/example.yaml`
    ```bash
    SOVEREIGN_CONFIG=file:///srv/sovereign/example.yaml
    ```
    
Multiple configuration files can also be specified, and values will be replaced by the rightmost specified file.

!!! example

    Common example: 
    
    * Configuration file with common settings
    * Configuration file with deployment or environment specific settings
        
    ```bash
    SOVEREIGN_CONFIG=file:///srv/common.yaml,file:///srv/environments/production.yaml
    ```
    
    Any values in `production.yaml` will _**merge**_ over the top of `common.yaml`.

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

### `node_matching`
Whether Sovereign should compare the configured node & source keys. If set to False, all sources will be used when generating configuration.  
Defaults to True

### `templates`
A mapping of envoy version and template paths to use when responding to discovery requests.

See the [templates section of the tutorial](/tutorial/templates/#templates-for-specific-versions-of-envoy)
for more information

!!! snippet

    ```yaml
    templates:
        <envoy_version OR "default">:
            <discovery type>: <template path>
    ```

!!! example

    ```yaml
    templates:
        1.13.1:
            listeners: file+yaml://etc/envoy/listeners.yaml
    ```

### `template_context`
A mapping of variable names and loadable paths to make available in templates.

A 'loadable path' means that # TODO add config loader info

### `refresh_context`
Whether or not to continually reload template context. Default is False.

### `context_refresh_rate`
How often (in seconds) Sovereign should reload template context. Defaults to 3600.
  
### `context_cache_size`
How many copies of context to keep in the LRU cache. Default is 1000.

### `modifiers`

A list of modifiers that should be applied to [Sources](/terminology/#sources).  
These modifiers can only access and modify one instance at a time.

See the [modifiers](/advanced/modifiers) page under advanced for info on how to set this up.

### `global_modifiers`

A list of global modifiers that should be applied to [Sources](/terminology/#sources).
These modifiers can access the entire [Instances](/terminology/#instances) object, therefore 
applying modifications that can span across instances.

See the [modifiers](/advanced/modifiers) page under advanced for info on how to set this up.

### `debug_enabled`
Enable tracebacks and extra detail in certain HTTP error responses.

### `environment`
An environment string mainly used for logging purposes.

### `sentry_dsn`
If Sovereign has been installed with Sentry (via ``pip install sovereign[sentry]``), the DSN to send Sentry events to.

### `auth_enabled`
Controls whether or not Sovereign will reject XDS requests that do not contain auth. Default is false.

For information on how to enable and supply authentication in XDS requests, see :ref:`Authentication`

### `auth_passwords`
A list of strings that are considered valid for authentication. When Sovereign receives a
request from an Envoy proxy, it checks for an ``auth`` field in the node metadata.
Sovereign attempts to decrypt the field, and checks if it is in this list of strings.

**It is recommended to set this option via the environment variable ``SOVEREIGN_AUTH_PASSWORDS``.**

!!! danger
    These passwords allow a person to authenticate to Sovereign and download configuration in plain-text.

### `encryption_key`
The Fernet key that Sovereign will use to encrypt/decrypt data.

**It is recommended to set this option via the environment variable ``SOVEREIGN_ENCRYPTION_KEY``.**

!!! danger
    This key can be used to decrypt any data that has been encrypted by it and then stored, for example in version control.

### `statsd`

#### `enabled`
Whether or not to emit statsd metrics

#### `host`
Where to emit statsd metrics

#### `port`
Port to use when emitting metrics to above host

#### `tags`
A key:value map of <tag name>: <tag value>
The value can be preceded by a scheme that allows usage of config loaders TODO CONFIG LOADER DOCO :(.

!!! example

    ```yaml
    statsd:
      tags:
        environment: 'env://SERVICE_ENVIRONMENT'
    ```

#### `namespace`
Suffix for all emitted metrics. Default is ``sovereign``
See :ref:`Metrics` for a list of metrics emitted.

### `dns_hard_fail`
When set to True, Sovereign will raise a HTTP exception for any DNS resolution failures that occur when using
the  ``sovereign.utils.eds:locality_lb_endpoints`` utility.

If False, it will return the supplied DNS name instead of IP addresses. This may cause Envoy to fail to load the configuration.

Default is False.

### `enable_access_logs`
Whether or not to emit HTTP request logs for discovery requests and other endpoints.  
Logs are JSON formatted.

Defualt is True.

## Full configuration example

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
    context_cache_size: 1000
    
    debug_enabled: no
    environment: production
    
    sentry_dsn: sentry://blahfoobar
    
    encryption_key: you_should_use_environment_variables_for_this!
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
    
Most if not *all* of the following settings should have an equivalent in the above configuration settings.

If an environment variable is set, but a different value is set in a configuration file, 
the value supplied by the configuration file will take precedence.

Environment Variable  | Default           | Description
--------------------- | ----------------- | ----------------------------
CONFIG                | None              | Where sovereign should look for it's configuration
HOST                  | 0.0.0.0           | What address the server will listen on
PORT                  | 8080              | What port the server will listen on
DEBUG                 | False             | Controls whether the server will log debug messages and tracebacks
ENVIRONMENT_TYPE      | local             | A label that indicates what environment the server is running in
AUTH_ENABLED          | False             | Controls whether Sovereign will check node metadata for an encrypted authentication string
AUTH_PASSWORDS        | None              | A list of passwords that Sovereign will consider valid for decrypted authentication strings
ENCRYPTION_KEY        | None              | A Fernet key for asymmetric encryption/decryption
NOCHANGE_RESPONSE     | 304               | What HTTP status should Sovereign return when it detects that the requesting node's config is up-to-date
SOURCE_MATCH_KEY      | service_clusters  | What value in Source data should sovereign look for when matching nodes
NODE_MATCH_KEY        | cluster           | What value in the Node Discovery Request should sovereign look for when matching nodes
MATCHING_ENABLED      | True              | Whether Sovereign should compare the configured node & source keys
REFRESH_CONTEXT       | False             | Whether or not to continually reload template context
CONTEXT_REFRESH_RATE  | 3600              | How often (in seconds) Sovereign should reload template context
CONTEXT_CACHE_SIZE    | 1000              | How many copies of cached context that Sovereign should keep
SOURCES_REFRESH_RATE  | 30                | How often (in seconds) Sovereign should reload sources (Cannot be disabled)
DNS_HARD_FAIL         | False             | Whether Sovereign should return a HTTP 500 when it can't resolve the address of an endpoint
ENABLE_ACCESS_LOGS    | True              | Whether or not to emit HTTP request logs for discovery requests
KEEPALIVE             | 5                 | How long the server should hold connections open for clients before closing
SENTRY_DSN            | None              | An optional Sentry DSN to send exceptions to
