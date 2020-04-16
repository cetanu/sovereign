.. _Metrics:

Metrics
=======

.. csv-table::
  :header: Name, Type, Description
  :widths: 1, 1, 2

    * discovery.rq_total,Counter,Total discovery requests
    * discovery.rq_ms,Histogram,Request time milliseconds
    * discovery.auth.success,Counter,Successful authenticated requests
    * discovery.auth.failed,Counter,Failed authenticated requests
    * discovery.auth.ms,Histogram,Time taken to authenticate requests
    * discovery.context.bytes,Histogram,Size of context in bytes
    * dns.resolve_ms,Histogram,Time taken to resolve an address
    * sources.refreshed,Counter,How many times sources have been updated during polling
    * sources.unchanged,Counter,How many times sources have been polled and had no changes
    * sources.error,Counter,How many times sovereign encountered an error when trying to refresh sources
    * cache.hit,Counter,How many memoized functions had their cached value reused
    * cache.miss,Counter,How many memoized functions were accessed after their last result expired
    * modifiers.apply_ms,Histogram,Time taken to apply all modifiers
