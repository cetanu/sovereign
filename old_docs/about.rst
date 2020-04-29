What is Sovereign?
==================
This Python package can be used to create a management server to control
and configure Envoy proxies.

The server created with this package will expose a JSON REST-API,
which a fleet of Envoy proxies can periodically poll for configuration changes.

How does it work?
-----------------
Sovereign is relatively simple, but can be powerfully extended.

A basic case looks like the following:

1. Configure a **Source** that Sovereign will poll periodically for data
2. Write **templates** for different kinds of Envoy discovery requests, add them to Sovereigns config
3. Host Sovereign somewhere, and have Envoy proxies poll it for configuration

This can then be extended with authentication, node matching, encryption, and so on.

See the :ref:`tutorial` for a quickstart.
