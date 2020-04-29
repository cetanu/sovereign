Changelog
=========

0.7.2 29-04-2020
----------------

* Added configurable cache strategy for Sovereign 304 responses (when config hasn't changed).
  Sovereign can be configured to base the version of the configuration on the context (data used to create config)
  or the content (the config after being rendered using context).
* Removed context cache, since it didn't seem to be effective
* Templates will cache their jinja AST and source checksum for a slight performance improvement

0.7.1 17-04-2020
----------------

* bugfix: modifiers were applying to out-of-date instances

0.7.0 16-04-2020 -- Deleted from PyPI
-------------------------------------

* Sovereign requires **Python>3.8.0** as of this version

* sources: New argument for sources: `scope`  

   This allows adding a source that will be 'scoped' to a single discovery type.  
   For example, if a source only contains data for clusters, or routes, the scope can be set to `clusters` or `routes`.  
   That data will then be available in templates in a variable named after the resource type eg. `clusters`.  
   To have a source be available in all templates, leave the scope blank or put `default` and it will be available 
   via the variable `instances` to maintain backward compatibility.

* internal: replace custom cached properties with functools.cached_property
* logging: YAML parsing errors will now emit a log message
* logging: Added some log messages to indicate that Sovereign has started
* bugfix: if node matching was disabled, the web interface would break when trying to determine service clusters
* config: if no config file is specified via SOVEREIGN_CONFIG, Sovereign will look for a file at /etc/sovereign.yaml
* caching: [template context](https://vsyrakis.bitbucket.io/sovereign/docs/html/guides/tutorial.html#adding-template-context)
           (including the global `instances` variable available in templates) 
           is now cacheable using the config option `context_cache_size` 
           or environment variable `SOVEREIGN_CONTEXT_CACHE_SIZE`.  
           Default is 1000;
           this means 1000 different combinations of requests (node + xds type + resource names + sources).  
           This uses a LRU cache, so the option caches a number of executions rather than
           for a specific amount of time.  
           A new metric is emitted for this: `sovereign.discovery.context.bytes`

0.6.17 2020-03-24
-----------------

* bugfix: removed max_age from ui cookies since it caused them to stop working somehow

0.6.16 2020-03-12
-----------------

* discovery: the host header provided to sovereign is now available as 'host_header' in templates

0.6.15 2020-03-04
-----------------

* serialization: added support for ORJSON; install bundled with `pip install sovereign[orjson]`

0.6.14 2020-02-26
-----------------

* bugfix: sometimes during discovery, there would be no resources rendered, resulting in a runtime error
* ui: added a max-age to cookies set in the ui
* metrics: added timing for authentication
* performance: reading from sources is now cached in-between refreshes
* performance: glom is only used to perform node-matching if the keys involved are complex/nested
* performance: utils.eds.locality_lb_endpoints was performing a deepcopy unnecessarily in cases where there is only a single endpoint
* performance: node-matching conditions is now supplied by a generator which means it exits as soon as one condition evaluates as true
* performance: templates loaded by sovereign at startup will store their code/template/content upon being initially loaded
* cache: removed threshold limit of 10 items, which means it is now the default (500 items)

0.6.13 2020-02-18
-----------------

* bugfix: node matching would still be evaluated even if it was disabled. aka sovereign would still check for the default source key "service_clusters".
* discovery: sovereign will check if the envoy proxy has supplied its build version in the envoy v3 api format

0.6.12 2020-02-06
-----------------

* bugfix: ImportError when no auth/crypto key is provided and the default is used (empty string)

0.6.11 2020-01-21
-----------------

* perf: added a 60 second cache to modifiers, as they are typically injected as an entry point at install-time, therefore
        should execute the same way almost all the time.
* stats: added an object that fixes the /stats endpoint not displaying emitted stats when statsd is enabled
* swagger doc: updated descriptions of a few endpoints
* removed /request_id debugging endpoint

0.6.10 2020-01-17
-----------------

* bugfix: not supplying a fernet key would result in an exception, even if auth/crypto is not used
* improvement: loading environment variables will now produce a better error when they are missing/can't be loaded

0.6.9 2020-01-16
----------------

* bugfix: changes made to source refreshing may have resulted in sovereign only refreshing them once upon startup.
          Added more metrics, and sovereign will force a refresh of sources if they become stale.
          In addition, instead of having a separate thread to poll sources, it is now a middleware, as the thread proved
          unreliable.

0.6.8 2020-01-15
----------------

* sentry: removed sentry-asgi dependency as the sentry-sdk now supports starlette
* ui: fixed the virtualhosts list only sorting the first item
* sources: made the thread that polls sources more resilient by continuing after any sort of failure... might add
           some logic that kills the server in the event of catastrophic failure.

0.6.7 2020-01-14
----------------

* logs: the setting debug_enabled/SOVEREIGN_DEBUG will now enable/disable debug log messages.
* sources: sources are now polled continuously in the background in a single thread instead of a thread being created 
           after each discovery response.

0.6.6 2019-12-19
----------------

* bugfix: the version of supplied xds resource configuration is now also based on the name of the requested resources

0.6.5 2019-12-18
----------------

* server script: removed bash script in favor of a python script
* server script: number of workers/threads can now be overridden with environment variables
* sources: changed sovereign to stop attempting to refresh sources if an error is encountered, + log a message/metric for this
* sources: removed metrics for swap_time and poll_time
* updated docs

0.6.4 2019-12-12
----------------

* middleware: metrics middleware will not add certain tags if they are empty. This mainly affects requests that resulted in a HTTP 500.

0.6.3 2019-12-09
----------------

* middleware: fixed metrics not being added to the application
* amended tests to make sure metrics are being incremented
* added route `/admin/stats` for seeing which stats have been incremented and how many times


0.6.2 2019-12-09
----------------

* middleware: separated logging/metrics middleware into two separate middlewares
* middleware: made metrics middleware ignore failures and log an error instead

0.6.1 2019-12-06
----------------

* discovery: fixed a bug where proprietary headers were not being included in discovery responses, leading to metrics being missed

0.6.0 2019-12-05
----------------

* ui: the routes page won't display virtualhosts if they are the only virtualhost within a route configuration
* ui: fixed a minor issue in top nav where selecting routes would highlight both routes and scoped-routes
* ui: made discovery responses used to generate ui a tiny bit more efficient
* assets: updated screenshot of the ui
* discovery: stop sending body with 304 response status (against HTTP RFC)
* discovery: cached responses now only emit 304 (config option removed)
* discovery: removed client_ip tag from discovery.rq_total metric
* openapi: added model to discovery route so that there is an example in /docs

#### Reworked metrics

Since metrics for HTTP requests were only being emitted for discovery endpoints, and various other metrics that 
were introduced prior to performance improvements in sovereign, the following changes were made:

* Replaced `rq_ms` metric with `discovery.rq_ms`
* Removed:
    * `discovery.total_ms`
    * `discovery.version_hash_ms`
    * `discovery.render_ms`
    * `discovery.deserialize_ms`
* Removed the `resource` tag from `discovery.rq_ms` & `discovery.rq_total`
* Sovereign will include several headers on discovery responses:
    * `X-Sovereign-Client-Version`: The build version of the envoy proxy as indicated by the discovery request
    * `X-Sovereign-Requested-Resources`: The resource names that the envoy proxy requested
    * `X-Sovereign-Requested-Type`: The type of discovery that was requested (clusters/listeners/etc)
    * `X-Sovereign-Response-Version`: The version_info of the resulting configuration
* The above headers are used by middleware to tag the metrics: `discovery.rq_ms` & `discovery.rq_total`


0.5.13 2019-11-29
-----------------

* discovery: derive "discovery_types" enum from all configured discovery types, across all envoy versions
* ui: added a count for all resource types
* ui: added support for selecting which envoy version templates should be rendered as
* ui: added support for filtering resources by service cluster/source match key
* ui: '/' now redirects to the UI instead of docs
* ui: Handle case where a version/service-cluster combination results in an error


0.5.12 2019-11-14
-----------------

* routes: fixed `/admin/xds_dump` emitting an error when it encountered an object that it doesn't know how to serialize to json

0.5.11 2019-11-01
-----------------

* routes: removed `/admin/cache_dump` since it's been mostly rendered useless by smarter source polling
* config: added an option "enable_access_logs" to toggle whether or not to emit logs for http requests


0.5.10 2019-10-10
-----------------

* init: removed startup log message
* init: refactored module to be a lot simpler, also changed it so that sovereign will crash if not provided configuration
* logging: switched to using thread-local for structlog, which allows adding context to log messages from other parts of the app
* logging: added back resource_names/envoy_ver to discovery request logs, since this was removed when fastapi was introduced
* repo: added a screenshot of the ui to the readme
* schemas: added a `common` property to the `Node` pydantic model that returns fields that are typically not unique from node to node
* schemas: added `xds_templates` property to the `SovereignConfig` model, to simplify the init process
* discovery: removed debug keyword argument from discovery.response; this is now controlled by `debug_enabled` in configuration
* discovery: the `debug` variable will no longer appear in template context
* discovery: moved most of the code related to building template context to the `make_context()` function
* discovery: simplified the values passed in to `parse_envoy_configuration()`, this may prove useful later if we decide to apply caching to this function
* discovery: added the basis for unit tests which will be useful for benchmarking later on
* discovery/templates: added the ability to specify python templates, which avoids the cost of having to use jinja template rendering + deserialization. 
  See [Adding Python templates](https://vsyrakis.bitbucket.io/sovereign/docs/html/guides/tutorial.html#python-templates) in the tutorial for more details.
* config_loaders: added python loader for the above change. Probably not usable for anything else but templates at the moment.
* tests: added starlette test client to perform unit tests which execute fastapi routing code and provide accurate coverage
* tests: added semi-benchmarking unit tests for discovery, particularly for the use-case where an envoy has 10,000 clusters

0.5.9 2019-09-25
----------------

* Forgot to add ``aiofiles`` to dependecies... which is needed to serve CSS for the UI. :disappointed:

0.5.8 2019-09-25
----------------

* Added gunicorn, which will run sovereign with the uvicorn worker class
* Bugfix: logging - Fixed ``uri_path`` including the scheme/host
* Upgraded resource user interface CSS, looks fancy now

0.5.7 2019-09-24
----------------

* DNS failures during ``sovereign.utils.eds:locality_lb_endpoints`` will now only raise if dns_hard_fail is set to True in configuration
* Refactored ``sovereign.discovery`` so that parsing the rendered YAML happens as a second step, in a way that does not modify the original list of resources.
* Added tests to ensure above change is consistent
* Added a way to safely represent the current configuration, and then added an endpoint that displays it
* Configurations that enable statsd but haven't installed it will result in an error

0.5.6 2019-09-24
----------------

* Changed dns utility to raise a HTTP Exception with the details instead of a Lookup error that would result in a traceback

0.5.5 2019-09-24
----------------

* Bugfix: PyYAML requirement has to be installed from PyPI

0.5.4 2019-09-23
----------------

* Bugfix: request duration metric was being reported inaccurately due to being provided in seconds, but measured in milliseconds
* Added a custom list type which automatically handles resource names requested by envoy proxies.
  This means that a template can declare resources, without having to use `if` conditionals
  to return specifically what a proxy has requested. If the envoy proxy does not specify any resource names, Sovereign will return
  all resources from the template.
* The above change also fixes some issues with the resource UI
* Made the installation of ujson and statsd optional. Install with (Example: `pip install sovereign[ujson,statsd]`)

0.5.3 2019-09-20
----------------

* Replaced all instances of dataclasses with pydantic models
* Added a *really* basic UI that can be used to browse the current XDS config of the server.
  Will iterate on this in future releases.

0.5.2 2019-09-19
----------------

* ``/admin/source_dump`` uses a JSON encoder that supports complex python types, in the case that a Modifier inserts them.

0.5.1 2019-09-19
----------------

* Added UJSON serializer as an option when loading config and sources
* Added an optional boto dependency that can be used to load S3 buckets with paths such as ``s3+ujson://my-bucket-name/file.json``.
  You can get sovereign bundled with boto with ``pip install sovereign[boto]``

0.5.0 2019-09-19
----------------

* Migrated from Quart (and Hypercorn) to FastAPI (Starlette/Uvicorn).
    * Sovereign now has a ``/docs`` endpoint which should be helpful!
    * Better request/response validation
    * Clearer data schemas for all endpoints
    * More maintainable codebase into the future
    * Cleaner middleware system
    * Some performance improvements in serialization

0.4.2 2019-09-13
----------------

* Bugfix weighted_clusters utility not actually normalizing the weights up to a default total weight of 100
* Bugfix template_context refresh schedule did not have a unit (changed to 'seconds')

0.4.1 2019-09-11
----------------

* Fixed UUID being an object instead of a string when logged
* Pinned h11 back to 0.7

0.4.0 2019-09-11
----------------

* Bumped versions of some pinned dependencies (quart, hypercorn, h11)
* Changed some exceptions with regard to cryptographic operations, they now typically return either HTTP 400 or 401
* Replaced werkzeug exceptions with Quart exceptions
* Added simple request-id to every request
* Removed flask-request-id dependency
* Removed flask patch
* Added code that checks templates and removes variables from template context if they are not declared/used within the template.
  This means that if context that's not relevant to the template changes, it won't affect the version of the configuration.

0.3.3 2019-09-10
----------------

* Changed config file loading to use dictupdate utility to merge multiple config files, overwriting values with the rightmost config file
* Added the ability to configure whether or not **template context** is periodically reloaded.

0.3.2 2019-09-06
----------------

* Bugfix: HTTP config loader was deserializing the text of a request even for 5xx responses. Now raises.

0.3.1 2019-09-05
---------------

* Bugfix: when matching nodes to sources, the original source data could sometimes be transformed in-place by custom
  modifiers and/or global modifiers. This would not result in a change in configuration, but the version_info string
  would be slightly different, causing a 200 and full response to be returned to envoy clients, instead of a 304 Not Modified.

0.3.0 2019-09-03
----------------

* Overrided the default Quart JSON encoder with one that catches type errors for unknown objects.
* Added the schedule library to poll sources on a configurable interval.
  Sources are now refreshed during the teardown of a request, and only when pending according to the schedule.
  This will remove cases where a cache miss causes a request to have to wait for sovereign to 
  refresh the source before serving out the response.
* Renamed some functions in the sources module so they make more sense.
* Added glom for source/node matching so that either matching key can be specified as 'key.nested_key.second_nested_key'
* Removed the "service broker" source since the file source supersedes it
* Added more validation to configuration options and types by switching to pydantic dataclasses
* Added configuration options that allow specification of a source_match_key and node_match_key
  These options will look for a key within all instances polled from sources, and then look for the corresponding key
  in the "Node" of an Envoy Discovery Request. If both values match, or the source contains the value from the node, 
  then the instance will be added to template context for rendering.
* Reworked tests to more explicitly test the interaction between source_match_key and node_match_key
* Added a bunch of unit tests


0.2.5 2019-08-28
----------------

* Added bytes_in/bytes_out to logging based on the content-length of the request/response respectively.
* Removed the envoy node id and metadata from the arguments used to create the version_info of configuration so that 
  all nodes within a (cluster, build_version) grouping would receive consistent versions.

0.2.4 2019-08-27
----------------

* Pinned hypercorn (ASGI server) version to 0.7.2

0.2.3 2019-08-27
----------------

* Moved authentication to ``sovereign.views.discovery.discovery_endpoint`` from ``sovereign.discovery``. 
  This is to fix the ``/admin/xds_dump`` endpoint from requiring auth.
* Added a bit more detail (what XDS type, what envoy version) for errors produced when a template fails
  to be parsed as valid YAML.
* Bugfix ``/admin/xds_dump`` view not awaiting discovery response coroutine
* Updated mock_discovery request to return the DiscoveryRequest dataclass instead of dictionary
* Added crypto utils to template context by default
* Made ``/admin/xds_dump`` slightly safer by introducing metadata in the mock discovery request which 
  signals sovereign to hide private keys, which sovereign does by swapping the crypto utilities with a dummy one.

0.2.2 2019-08-23
----------------

* Fixed a bug that would cause statsd tags to be parsed as simple strings instead of using a config loader to evaluate them.
* Made discovery requests not require a locality
* Made discovery requests return 'default' when the build version string cannot be parsed
* Fixed template_context being a required configuration option
* Fixed auth always being enabled

0.2.1 2019-08-23
----------------

* Removed authentication working by providing simply a string that is decryptable, 
  without caring what the content of the string is

0.2.0 2019-08-22
----------------

* Introduced a few dataclasses to structure and validate the configuration options that sovereign has available.
* Added the ability to configure a list of strings that are valid auth secrets. 
  When auth is enabled, envoys must provide auth that when decrypted, matches at least one of these strings.
  Envoy proxies can provide these via their node metadata.
* Related to the above point, deprecated authentication working by providing simply a string that is decryptable, 
  without caring what the content of the string is.
* Expanded the available configuration options and associated documentation.
* Added dataclasses for discovery requests

0.1.30 2019-08-18
-----------------

* utils.eds.locality_lb_endpoints: Skip zone-aware load-balancing for upstreams with a single zone
* Bugfix: /admin/xds_dump endpoint was returning no resources due to the mock discovery request having a version of '0',
  which indicated to sovereign that it should return early with No Change.

0.1.29 2019-08-16
-----------------

* Bugfix: Since switching version_hash to use the data from pre-jinja-rendering & YAML serialization, it has been hashing based on data which
  may not be the same from machine to machine. Templates loaded using Jinja2 in particular (which is the suggested way of configuring sovereign)
  had a string representation that was simply the memory address of the template. This is different from machine to machine, so the version_info
  that was generated as a result and handed to Envoy proxies was different depending on which server responded to it.
* Templates loaded via config will also store a checksum if possible, to aid with the above point.
* Also switched the hashing algo to zlib.adler32 since this is deterministic, high performance, and we don't need the security of an md5 hash or similar for versioning.
* Enabled async for jinja2 rendering

0.1.28 2019-08-16
-----------------

* Added /version endpoint to determine what version of sovereign is running

0.1.27 2019-08-16
-----------------

* Bugfix: version_hash was non-deterministic resulting in different version info strings per control-plane (different hashing seed)

0.1.26 2019-08-15
-----------------

* Bugfix: version_hash producing different versions on each execution due to receiving differently ordered Discovery Requests.

0.1.25 2019-08-15
-----------------

* The function that calculates the version number for configuration has been changed to use python's in-built ``hash()`` function.
  The previous implementation (taking a sha256 hash of the YAML serialized config) was too expensive and the level of security provided by
  such a hashing function is not required here.
* The version hash is now based on the (template content + template context + envoy node data) whereas before it was based on
  the configuration AFTER it has been rendered together. This allows Sovereign to return a non-200 earlier.
* Added a jitter argument to the memoize decorator to allow randomizing the cache timeout.
* Added 'cache_timeout' and 'cache_jitter' as config options to the file Source.

0.1.24 2019-08-15
-----------------

* Added more statsd metrics to measure the complete time to discovery including serialization and version hashing

0.1.23 2019-06-24
-----------------

* Bugfix: Sentry Flask integration replaced with sentry-asgi

0.1.22 2019-06-19
-----------------

* Bugfix: `/admin/xds_dump` endpoint was casting the query parameter `resource_names` as a string, when it should be a list
* Bugfix: quart.flask_patch needs to be imported before the Sentry Flask integration

0.1.21 2019-06-05
-----------------

* Changed /healthcheck endpoint to no longer test rendering, and instead just return OK. Rendering test moved to /deepcheck
* Added ability to specify an optional Sentry DSN to send exceptions to. Environment variable for this is `SOVEREIGN_SENTRY_DSN`.
  Sovereign must be installed with `pip install sovereign[sentry]` to install the required packages.

0.1.20 2019-05-27
-----------------

* Changed /healthcheck endpoint to test rendering a random template type, instead of all of them, per execution

0.1.19 2019-05-23
-----------------

* Bugfix: if sources retrieved by sovereign aren't loadable as a dict, they will be skipped and a warning will be logged

0.1.18 2019-03-29
-----------------

* Add configuration options to specify port and constant tags for Statsd metrics

0.1.17 2019-03-22
-----------------

* Bugfix: an envoy without an ipv4 key in metadata would receive errors in response to a discovery request
* Return a customizable HTTP response code on 'cached' responses (i.e. responses with no changes)
  The default is 304, which at present causes Envoy to consider the request failed. Setting this to 504 will avoid
  emitting logs and metrics that indicate a failure, but will increase the 5xx statistics of the cluster.
  The option can be set in the config via `no_changes_response_code`
* werkzeug.contrib.cache has been deprecated in favor of cachelib, so we are now using the latter.

0.1.16 2019-02-19
-----------------

* Restructured the package init so that it doesn't throw an exception if config hasn't been supplied via environment variable
* The app will only emit metrics for request paths that are used for discovery

0.1.15 2019-01-25
-----------------

* Removed and simplified the repository by removing Atlassian specific items
* Updated documentation and associated release process

0.1.14 2019-01-25
-----------------
* Changes to an Atlassian-related Modifier. Going to try to remove this at some stage.
