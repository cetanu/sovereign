# Node Matching

Node matching helps sovereign to decide which instances it should use as data 
when serving out envoy configuration to proxies.

For example imagine that you have 3 sources, each being an API with different 
data such as endpoints, routes, and listeners.  
You may not want all of that data to be used when creating clusters, routes, 
and listeners for *every* envoy proxy that requests configuration from Sovereign.

If this isn't the case then you can turn node matching off entirely.

## Default node matching behavior

By default, Sovereign expects each Instance to have a key `service_clusters`, which it will compare with
a field named `cluster` which Envoy provides with each Discovery Request.  

The following example shows an instance which has to two service clusters, `group1` and `group2`

!!! example

    ```json
    [
        {
            "name": "instance1",
            "endpoints": [
                "server.local:8080"
            ],
            "service_clusters": [
                "group1",
                "group2"
            ]
        }
    ]
    ```
    
And an envoy proxy will make a discovery request which might look like:

!!! example

    ```json
    {
      "node": {
        "cluster": "group1",
        "metadata": {
          "instance_size": "small"
        },
        "build_version": "e5f864a82d4f27110359daa2fbdcb12d99e415b9/1.9.0/Clean/RELEASE"
      },
      "resource_names": [],
      "version_info": "0"
    }
    ```

Since the proxy has a cluster with `group1`, Sovereign will include the above Instance 
when generating configuration.

## Choosing which keys to compare

### The node match key

Using the above discovery request example, we could select a different key to match on.

For example, if you wanted to provide different configuration based on the metadata, you could 
change the [node match key](/settings/#node_key) as follows:

!!! example

    ```yaml
    matching: 
      node_key: metadata.instance_size
    ```
    
This means that sovereign will use instances with `service_clusters` that contain `small`.  

### The source match key

Say for example your source data doesn't contain a key named `service_clusters` - you can change the
[source match key](/settings/#source_key) in the same way as above.
