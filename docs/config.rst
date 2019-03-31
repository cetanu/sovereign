Configuration Options
---------------------

Sovereign accepts a yaml/json/jinja2 file as configuration.

The following options are supported:

auth_enabled
  (bool) Controls whether or not Sovereign will reject XDS requests that do not contain auth. Default is false.

  For information on how to enable and supply authentication in XDS requests, see :ref:`Authentication`


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
  Default is 504 (Gateway Timeout).

.. work in progress below

.. templates
.. template_context
.. sources

.. regions
.. eds_priority_matrix
