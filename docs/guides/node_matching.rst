.. _node_matching:

Node Matching
-------------
Sovereign was built with multiple distinct clusters of Envoy proxies in mind.

Initially, there was a hardcoded way to determine which data should be provided to proxies, which was
to check the service cluster of an Envoy, and match it against a key in Source data named "service_clusters".

As of 0.2.6 this is configurable via ``source_match_key`` and ``node_match_key``.

Example matching
''''''''''''''''
The following example works for the default Sovereign configuration.

Say for example you have a source that returns the following data:

.. code-block:: json
   :linenos:

   [
      {
         "name": "company_cluster_01",
         "backends": [
             "cc01-a.company.com",
             "cc01-b.company.com",
         ],
         "service_clusters": [
            "cc01"
         ]
      }
   ]

And now say for example you've deployed a fleet of Envoy proxies, each grouped by service cluster.
Following the above source, we can imagine the service clusters may be named cc01, cc02, cc03, and so on.

.. note::

    You can specify the service cluster of an envoy proxy via its commandline like so:

    .. code-block::

       envoy --config /etc/envoy.yaml --service-cluster cc01

When the envoy proxy sends a discovery request, it will look something like this:

.. code-block:: json
   :linenos:

   {
       "version_info": "0",
       "node": {
           "cluster": "cc01",
           "build_version": "<revision hash>/<version>/Clean/RELEASE",
           "metadata": {
               "auth": "..."
           }
       }
   }

Note the service cluster on line 4.

If you're using the default sovereign configuration, Sovereign will include the ``company_cluster_01`` data
in a variable named ``instances``, which is available inside the templates used to render out Envoy config.

You can see examples of this in the tutorial, particularly in :ref:`adding_sources` and :ref:`dynamic_sources`
