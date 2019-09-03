.. _Metrics:

Metrics
=======

.. csv-table::
  :header: Name, Type, Description
  :widths: 1, 1, 2

    * discovery.render_ms,Histogram,Time taken to render a given XDS template
    * discovery.rq_total,Counter,Total discovery requests
    * discovery.auth.success,Counter,Successful authenticated requests
    * discovery.auth.failed,Counter,Failed authenticated requests
    * discovery.total_ms,Histogram,Time taken to gather context + render template + serialize config
    * discovery.version_hash_ms,Histogram,Time taken to calculate and add the version to config
    * dns.resolve_ms,Histogram,Time taken to resolve an address
    * sources.poll_time_ms,Histogram,Time taken to load all sources
    * sources.swap_time_ms,Histogram,Time taken to clear and refill sources with new data
    * sources.refreshed,Counter,How many times sources have been updated during polling
    * sources.unchanged,Counter,How many times sources have been polled and had no changes
    * cache.hit,Counter,How many memoized functions had their cached value reused
    * cache.miss,Counter,How many memoized functions were accessed after their last result expired
    * modifiers.apply_ms,Histogram,Time taken to apply all modifiers
    * rq_ms,Histogram,Request time milliseconds
