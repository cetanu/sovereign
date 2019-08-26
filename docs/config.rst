Configuration Options
---------------------

Sovereign accepts a YAML/JSON configuration file, specified in the environment variable ``SOVEREIGN_CONFIG``.
Example: ``SOVEREIGN_CONFIG=file:///etc/sovereign.yaml``

The following options are available:

templates
  (dict) A mapping of version:template_paths to use for discovery requests to sovereign.
  This mapping is flexible when it comes to versions and which templates you intend to use (you don't have to implement
  all of them).

  See :ref:`adding_templates` for examples.

template_context
  (dict) A mapping of variable names and loadable paths to make available in templates. A 'loadable path' means that it can
  be evaluated by :ref:`config_loaders`.

  See :ref:`adding_template_context` for examples.

application_host
  (string) What address the server will listen on. Defaults to '0.0.0.0'

application_port
  (int) What port the server will listen on. Defaults to 8080.

debug_enabled
  (bool) Enable tracebacks and extra detail in certain HTTP error responses.

environment
  (string) An environment string mainly used for logging purposes.

sentry_dsn
  (string) If Sovereign has been installed with Sentry (via ``pip install sovereign[sentry]``), the DSN to send Sentry events to.

auth_enabled
  (bool) Controls whether or not Sovereign will reject XDS requests that do not contain auth. Default is false.

  For information on how to enable and supply authentication in XDS requests, see :ref:`Authentication`

auth_passwords
  (list) A list of strings that are considered valid for authentication. When Sovereign receives a
  request from an Envoy proxy, it checks for an ``auth`` field in the node metadata.
  Sovereign attempts to decrypt the field, and checks if it is in this list of strings.

  It is recommended to set this option via the environment variable ``SOVEREIGN_AUTH_PASSWORDS``.

.. danger::
   These passwords allow a person to authenticate to Sovereign and download configuration in plaintext.

statsd
  enabled
    (bool) Whether or not to emit statsd metrics

  host
    (string) Where to emit statsd metrics

  port
    (int) Port to use when emitting metrics to above host

  tags
    (dict) A key:value map of <tag name>: <tag value>
    The value can be preceded by a scheme that allows extended config loading.

    Example:

    .. code-block:: yaml

       statsd:
         tags:
           environment: 'env://SERVICE_ENVIRONMENT'

  namespace
    (string) Suffix for all emitted metrics. Default is ``sovereign``
    See :ref:`Metrics` for a list of metrics emitted.

no_changes_response_code
  (int) What HTTP code to return to Envoy clients when there are no changes to their configuration.
  Default is 304 (Not Modified).

.. work in progress below

.. template_context
.. sources
.. regions
.. eds_priority_matrix

Environment Variables
---------------------

.. csv-table::
  :header: Environment Variable, Default, Description
  :widths: 1, 1, 2

    SOVEREIGN_HOST,0.0.0.0,What address the server will listen on
    SOVEREIGN_PORT,8080,What port the server will listen on
    SOVEREIGN_DEBUG,False,Controls whether the server will log debug messages
    SOVEREIGN_AUTH_ENABLED,False,Controls whether Sovereign will check node metadata for an encrypted authentication string
    SOVEREIGN_AUTH_PASSWORDS,None,A list of passwords that Sovereign will consider valid for decrypted authentication strings
    SOVEREIGN_ENCRYPTION_KEY,None,A Fernet key for asymmetric encryption
    SOVEREIGN_ENVIRONMENT_TYPE,local,A label that indicates what environment the server is running in
    SOVEREIGN_CONFIG,None,Where sovereign should look for it's configuration
    SOVEREIGN_SENTRY_DSN,None,An optional Sentry DSN to send exceptions to
    SOVEREIGN_NOCHANGE_RESPONSE,304,What HTTP status should Sovereign return when config is up-to-date
