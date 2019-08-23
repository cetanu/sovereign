.. _Metrics:

Metrics
=======

.. csv-table::
  :header: Name, Type, Description
  :widths: 1, 1, 2

    * sovereign.discovery.render_ms,Counter,Time taken to render a given XDS template
    * sovereign.discovery.total_ms,Counter,Time taken to gather context + render template + serialize config
    * sovereign.discovery.version_hash_ms,Counter,Time taken to calculate and add the version to config
    * sovereign.dns.resolve_ms,Counter,Time taken to resolve an address
    * sovereign.sources.load_ms,Counter,Time taken to load all sources
    * sovereign.modifiers.apply_ms,Counter,Time taken to apply all modifiers
    * sovereign.rq_ms,Counter,Request time milliseconds
    * sovereign.rq_total,Counter,Total requests
