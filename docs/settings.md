## Configuration Options

By default Sovereign will look for a YAML/JSON configuration file at `/etc/sovereign.yaml`

This can be overridden with the environment variable `SOVEREIGN_CONFIG`

!!! example

    Loading configuration from an alternate location, eg. `/srv/sovereign/example.yaml`
    ```bash
    SOVEREIGN_CONFIG=file:///srv/sovereign/example.yaml
    ```
    Take note of the `file://` prefix used to indicate that it comes from a location on-disk.
    
Multiple configuration files can also be specified, and values will be replaced by the _rightmost_ specified file.

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
          spec: 
            protocol: file
            serialization: yaml
            path: /etc/envoy/static_clusters.yaml
      # Listeners from an etcd cluster
      - type: file
        scope: listeners
        config:
          spec: 
            protocol: http
            serialization: json
            path: etcd.internal:8081/v2/keys/envoy_listeners
      # Other resources from an S3 bucket
      - type: file
        scope: default
        config:
          spec:
            protocol: s3
            serialization: json
            path: my-bucket-name:envoy_data.json
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

### `source_config`

Various settings to change how source polling behaves:

#### `refresh_rate`
How often (in seconds) Sovereign should refresh all sources. Defaults to 30.

#### `cache_strategy`
When Sovereign polls sources, it stores them in-memory until they are refreshed/changed.

When serving out discovery requests, sovereign uses the in-memory sources to decide whether or not
an Envoy proxy is up-to-date, based on their `"version_info"`.

This setting controls how sovereign makes this determination:

* `context`: Sovereign will compare a hash of various data (sources, template context, envoy node metadata) with the received envoy node version.
* `content`: Sovereign will fully render a response, and compare a hash of the contents with the received envoy node version.

### `matching`

Node matching configuration:

#### `enabled`
Whether Sovereign should compare the configured node & source keys. If set to False, all sources will be used when generating configuration.  
Defaults to True

#### `source_key`
What key to look for within sources when considering which data should be supplied to particular Envoy proxies.

#### `node_key`
What key to look for within the discovery request of an Envoy node, to see which source data it should be supplied with.

### `templates`
A mapping of envoy version and template paths to use when responding to discovery requests.

See the [templates section of the tutorial](/tutorial/templates/#templates-for-specific-versions-of-envoy)
for more information

!!! snippet

    ```yaml
    templates:
        <envoy_version OR "default">:
            type: <discovery type>
            spec:
              protocol: <file/http/s3/etc>
              serialization: <yaml/json/string/python/etc>
              path: <file path>
    ```

!!! example

    ```yaml
    templates:
        # Specific version, including patch version
        1.13.1:
            type: listeners
            spec: 
              protocol: file
              serialization: yaml
              path: /etc/envoy/listeners.yaml
        # Target all patch versions of a particular minor release
        1.14:
            type: listeners
            spec: 
              protocol: file
              serialization: yaml
              path: /etc/envoy/listeners.yaml
        # If none of the above match, use this one
        default:
            type: listeners
            spec: 
              protocol: file
              serialization: yaml
              path: /etc/envoy/listeners.yaml
    ```

### `template_context`
Template context is extra data that is included in all templates.

The specified context can be dynamically loaded, and reloaded on a schedule.

#### `context`
A mapping of variable names and loadable specifications to make available in templates.

!!! example

    Specifying template context

    ```yaml
    template_context:
      context:
        # Make a python module available as "ipaddress" in template markdown
        ipaddress:
          protocol: module
          path: ipaddress
      
        # Make a file available to all templates via markdown
        default_routes:
          protocol: file
          serialization: json
          path: /etc/stuff.json
    ```

!!! example

    Using template context within a template with the above example
    
    ```yaml
    # /etc/envoy/listeners.yaml
    
    resources:
      - name: listener
        address:
          socket_address:
            address: {{ ipaddress.IPv4Address(0)|string }}  # Makes "0.0.0.0"
            port_value: 80
            protocol: TCP
        filter_chains:
          - filters:
            - name: envoy.http_connection_manager
              config:
                stat_prefix: http
                codec_type: AUTO
                http_filters:
                  - name: envoy.router
                    config: {{ default_routes }}  # inlines the JSON blob
    ```

A 'loadable path' is a path that is interpreted by the [config loaders](/tutorial/first-steps#config-loaders) built into sovereign

#### `refresh`
Whether or not to continually reload template context. Default is False.

#### `refresh_rate`
How often (in seconds) Sovereign should reload template context. Defaults to 3600. (Only one of `refresh_rate` or `refresh_cron` can be set).

#### `refresh_cron`
Cron expression for when Sovereign should reload template context. (Only one of `refresh_rate` or `refresh_cron` can be set).

### `modifiers`

A list of modifiers that should be applied to [Sources](/terminology/#sources).  
These modifiers can only access and modify one instance at a time.

See the [modifiers](/advanced/modifiers) page under advanced for info on how to set this up.

### `global_modifiers`

A list of global modifiers that should be applied to [Sources](/terminology/#sources).
These modifiers can access the entire [Instances](/terminology/#instances) object, therefore 
applying modifications that can span across instances.

See the [modifiers](/advanced/modifiers) page under advanced for info on how to set this up.

### `debug`
Enable tracebacks and extra detail in certain HTTP error responses.

### `legacy_fields`

#### `environment`
An environment string mainly used for logging purposes.

This field is deprecated. Please specify environment in `logging` via `log_fmt` instead

#### `dns_hard_fail`
When set to True, Sovereign will raise a HTTP exception for any DNS resolution failures that occur when using
the  ``sovereign.utils.eds:locality_lb_endpoints`` utility.

If False, it will return the supplied DNS name instead of IP addresses. This may cause Envoy to fail to load the configuration.

Default is False.

This field is deprecated. It is suggested to supply a module via `template_context` that can perform
dns resolution in templates instead.

### `authentication`

Settings for authentication. It is strongly recommended to set these via environment variables.

#### `enabled`
Controls whether or not Sovereign will reject XDS requests that do not contain auth. Default is false.

For information on how to enable and supply authentication in XDS requests, see :ref:`Authentication`

#### `auth_passwords`
A list of strings that are considered valid for authentication. When Sovereign receives a
request from an Envoy proxy, it checks for an ``auth`` field in the node metadata.
Sovereign attempts to decrypt the field, and checks if it is in this list of strings.

**It is recommended to set this option via the environment variable ``SOVEREIGN_AUTH_PASSWORDS``.**

!!! danger
    These passwords allow a person to authenticate to Sovereign and download configuration in plain-text.

#### `encryption_key`
The Fernet key that Sovereign will use to encrypt/decrypt data.

**It is recommended to set this option via the environment variable ``SOVEREIGN_ENCRYPTION_KEY``.**

!!! danger
    This key can be used to decrypt any data that has been encrypted by it and then stored, for example in version control.

### `sentry_dsn`
If Sovereign has been installed with Sentry (via ``pip install sovereign[sentry]``), the DSN to send Sentry events to.


### `statsd`

#### `enabled`
Whether or not to emit statsd metrics

#### `host`
Where to emit statsd metrics

#### `port`
Port to use when emitting metrics to above host

#### `tags`
A key:value map of <tag name>: <tag value>
The value can be preceded by a scheme that allows usage of [config loaders](/tutorial/first-steps#config-loaders).

!!! example

    ```yaml
    statsd:
      tags:
        environment: 'env://SERVICE_ENVIRONMENT'
    ```

#### `namespace`
Suffix for all emitted metrics. Default is ``sovereign``
See :ref:`Metrics` for a list of metrics emitted.

### `logging`
Logging configuration

#### `application_logs`
Settings specifically for application logs, which are emitted when particular application events occur,
which may not be related to any discovery or other access.

##### `enabled`
Whether or not to emit application logs.  
Logs are JSON formatted.

Default is False.

#### `access_logs`
Settings specifically for access logs, which are emitted when any endpoint of sovereign is accessed.

##### `enabled`
Whether or not to emit HTTP request logs for discovery requests and other endpoints.  
Logs are JSON formatted.

Default is True.

##### `ignore_empty_fields`
If a log field is empty/blank, it will be omitted from the logs.

Default is True.

##### `log_fmt`
The log format to use for HTTP request logs.
This format should be a JSON encoded string.

The format supports the following keywords:

**ENVIRONMENT**
The environment set in configuration

**HOST**
The Host header provided by the HTTP client

**METHOD**
The method used by the HTTP client

**PATH**
The path portion of the URL provided by the HTTP client

**QUERY**
The query string provided by the HTTP client

**SOURCE_IP**
The source ip of the HTTP client

**SOURCE_PORT**
The source port of the HTTP client

**PID**
The process ID of the worker that processed the request

**USER_AGENT**
The user agent supplied by the HTTP client

**BYTES_RX**
Content size of the request

**BYTES_TX**
Content size of the response

**STATUS_CODE**
HTTP status code

**DURATION**
Time taken between receiving the request, and writing out the response

**REQUEST_ID**
A UUID to represent the request

**XDS_CLIENT_VERSION**
The version_info of the resource on the client-side

**XDS_SERVER_VERSION**
The version_info of the resource that sovereign responded with

**XDS_RESOURCES**
Which resources, by name, were requested

**XDS_ENVOY_VERSION**
The Envoy proxy version of the client

**TRACEBACK**
A Python traceback message, when a traceback occurs

**ERROR**
The name of the class of error, when an error occurs

**ERROR_DETAIL**
Further details about the error, if a description is available

#### Special fields for YAML errors

When troubleshooting a YAML issue, it may be useful to include all of the
following:

* YAML_CONTEXT
* YAML_CONTEXT_MARK
* YAML_NOTE
* YAML_PROBLEM
* YAML_PROBLEM_MARK


##### Default access log format

```json
{
    "env": "{ENVIRONMENT}",
    "site": "{HOST}",
    "method": "{METHOD}",
    "uri_path": "{PATH}",
    "uri_query": "{QUERY}",
    "src_ip": "{SOURCE_IP}",
    "src_port": "{SOURCE_PORT}",
    "pid": "{PID}",
    "user_agent": "{USER_AGENT}",
    "bytes_in": "{BYTES_RX}",
    "bytes_out": "{BYTES_TX}",
    "status": "{STATUS_CODE}",
    "duration": "{DURATION}",
    "request_id": "{REQUEST_ID}",
    "resource_version": "{XDS_CLIENT_VERSION} -> {XDS_SERVER_VERSION}",
    "resource_names": "{XDS_RESOURCES}",
    "envoy_ver": "{XDS_ENVOY_VERSION}",
    "traceback": "{TRACEBACK}",
    "error": "{ERROR}",
    "detail": "{ERROR_DETAIL}",
}
```



## Full configuration example

!!! example

    ```yaml
    sources:
      - type: <type>
        scope: 'default'
        config: {}
    
    source_config:
      refresh_rate: 30
      source_key: service_clusters
      node_key: cluster
    
    templates:
      default:
        type: clusters
        spec:
          protocol: file
          serialization: jinja2
          path: templates/default/clusters.yaml
        type: routes
        spec:
          protocol: file
          serialization: jinja2
          path: templates/default/routes.yaml
      1.12.0:
        type: clusters
        spec:
          protocol: file
          serialization: jinja2
          path: templates/1.12.x/clusters.yaml
        type: routes
        spec:
          protocol: file
          serialization: jinja2
          path: templates/1.12.x/routes.yaml
      1.13.0:
        type: clusters
        spec:
          protocol: file
          serialization: jinja2
          path: templates/1.13.x/clusters.yaml
        type: routes
        spec:
          protocol: file
          serialization: jinja2
          path: templates/1.13.x/routes.yaml
    
    template_context:
      context:
        region: 
          protocol: env
          path: DEPLOY_REGION
        environment: 
          protocol: env
          path: DEPLOY_ENV
        ip_acls:
          protocol: s3
          path: bucket-name:ips.json
      refresh: no
      refresh_rate: 3600
    
    debug: no
    
    sentry_dsn: sentry://blahfoobar
    
    authentication:
      enabled: yes
      encryption_key: you_should_use_environment_variables_for_this!
      auth_passwords:
        - VerySecretPassword1!
        - you_should_use_environment_variables_for_this!
    
    statsd:
      enabled: yes
      namespace: sovereign
      host: statsd-sink.internal
      port: 8125
      tags:
        region:
          protocol: env
          path: DEPLOY_REGION
        environment:
          protocol: env
          path: DEPLOY_ENV
        hostname: 
          protocol: env
          path: HOST
    
    logging:
      application_logs:
        enabled: no
      access_logs:
        enabled: yes
        ignore_empty_fields: yes
        log_fmt: |
            {
                "env": "{ENVIRONMENT}",
                "site": "{HOST}",
                "method": "{METHOD}",
                "uri_path": "{PATH}",
                "uri_query": "{QUERY}",
                "src_ip": "{SOURCE_IP}",
                "src_port": "{SOURCE_PORT}",
                "pid": "{PID}",
                "user_agent": "{USER_AGENT}",
                "bytes_in": "{BYTES_RX}",
                "bytes_out": "{BYTES_TX}",
                "status": "{STATUS_CODE}",
                "duration": "{DURATION}",
                "request_id": "{REQUEST_ID}",
                "resource_version": "{XDS_CLIENT_VERSION} -> {XDS_SERVER_VERSION}",
                "resource_names": "{XDS_RESOURCES}",
                "envoy_ver": "{XDS_ENVOY_VERSION}",
                "traceback": "{TRACEBACK}",
                "error": "{ERROR}",
                "detail": "{ERROR_DETAIL}",
            }
    ```

Environment Variables
---------------------

!!! info
    All of the following variables should be prefixed with `SOVEREIGN_`.  
    For example, `HOST` is `SOVEREIGN_HOST`
    
Most if not *all* of the following settings should have an equivalent in the above configuration settings.

If an environment variable is set, but a different value is set in a configuration file, 
the value supplied by the configuration file will take precedence.

Environment Variable    | Default                 | Description
----------------------- | ----------------------- | ----------------------------
CONFIG                  | None                    | Where sovereign should look for it's configuration
AUTH_ENABLED            | False                   | Controls whether Sovereign will check node metadata for an encrypted authentication string
AUTH_PASSWORDS          | None                    | A list of passwords that Sovereign will consider valid for decrypted authentication strings
ENCRYPTION_KEY          | None                    | A Fernet key for asymmetric encryption/decryption
NODE_MATCHING_ENABLED   | True                    | Whether Sovereign should compare the configured node & source keys
SOURCE_MATCH_KEY        | service_clusters        | What value in Source data should sovereign look for when matching nodes
NODE_MATCH_KEY          | cluster                 | What value in the Node Discovery Request should sovereign look for when matching nodes
REFRESH_CONTEXT         | False                   | Whether or not to continually reload template context
CONTEXT_REFRESH_RATE    | 3600                    | How often (in seconds) Sovereign should reload template context
CONTEXT_REFRESH_CRON    | None                    | Cron expression for when Sovereign should reload template context
CONTEXT_CACHE_SIZE      | 1000                    | How many copies of cached context that Sovereign should keep
SOURCES_REFRESH_RATE    | 30                      | How often (in seconds) Sovereign should reload sources (Cannot be disabled)
CACHE_STRATEGY          | context                 | What strategy Sovereign should use to determine if Envoy config is up to date
ENABLE_APPLICATION_LOGS | False                   | Whether or not to emit application logs
ENABLE_ACCESS_LOGS      | True                    | Whether or not to emit HTTP request logs for discovery requests
LOG_FORMAT              | [Default log format][1] | What fields to include in HTTP request logs
LOG_IGNORE_EMPTY        | True                    | Omit empty fields from logs
SENTRY_DSN              | None                    | An optional Sentry DSN to send exceptions to
DEBUG                   | False                   | Controls whether the server will log debug messages and tracebacks
HOST                    | 0.0.0.0                 | What address the server will listen on
PORT                    | 8080                    | What port the server will listen on
KEEPALIVE               | 5                       | How long the server should hold connections open for clients before closing
WORKERS                 | (cores * 2) + 1         | How many sovereign worker processes should be spawned
WORKER_TIMEOUT          | 30                      | How long a worker can be idle before it will be restarted
THREADS                 | 1                       | How many threads each worker should use for handling requests
PRELOAD                 | False                   | Whether the app should be preloaded before forking into worker processes

[1]: /settings/#default-access-log-format
