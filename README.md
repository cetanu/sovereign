sovereign
=========

Mission statement
-----------------
This project implements a JSON control-plane based on the envoy data-plane-api 
(<https://envoyproxy.io> , <https://github.com/envoyproxy/data-plane-api>)

The purpose of `sovereign` is to supply downstream envoy proxies with 
configuration in near-realtime by responding to discovery requests.

Features
--------
1. Accepts data from source(s) e.g. file, http, custom
2. (optional) Applies modifications to the received data
3. Renders the data into a Jinja2 template (or returns a static response)
4. Serializes the rendered configuration as JSON and returns it to the Envoy proxy

The idea behind this architecture is to enable high-extensibility.  
Users can add their own entry point to the package (todo: documentation) which the control-plane
will automatically use to retrieve data to be turned into configuration on the fly.

Requirements
------------
* Python 3.7+

Installation
------------
```
pip install sovereign
```

Local development
=================

Requirements
------------
* Docker
* Docker-compose

Installing dependencies for dev
-------------------------------
I recommend creating a virtualenv before doing any dev work

```
python3 -m venv venv
source venv/bin/activate
pip install -r requirements-dev.txt
```

Running locally
---------------
Running the test env

```
make run
```
    
Running the test env daemonized

```
make run-daemon
```

Pylint

```
make lint
```

Unit tests

```
make unit
```

Acceptance tests

```
make run-daemon acceptance
```
