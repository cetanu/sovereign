# Running the server locally

## Recap before running the server

The previous sections introduced the basic parts that are required for running Sovereign:

* In Sources, we configured cluster 'scoped' `inline` sources with a basic example of what the real data might look like.
* In Templates, we configured a YAML or Python template that will take the inline source and use it as information when generating the final result.

If you've already installed Sovereign and have completed the last two sections, then you can run the server with

```bash
$ sovereign

{"event": "Initial fetch of Sources", "level": "info", "timestamp": "2020-04-04T04:52:14.937402"}
{"event": "Sovereign started and listening on 0.0.0.0:8080", "level": "info", "timestamp": "2020-04-04T04:52:14.942280"}
```

You should then be able to visit the server locally by browsing to [http://localhost:8080](http://localhost:8080)

## Checking the Sovereign Interface

Upon browsing to Sovereign locally, you'll be redirected to its web interface.  
This web interface is read-only, and was created to enable quickly inspecting and troubleshooting issues with configuration.

We can use this interface now to see the configuration that the combination of our sources and templates have generated.
