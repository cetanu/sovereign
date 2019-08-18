Changelog
=========

0.1.30 2019-08-18
-----------------

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
