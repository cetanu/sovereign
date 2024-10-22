sovereign
=========


Mission statement
-----------------
This project implements a JSON control-plane based on the [envoy](https://envoyproxy.io) [data-plane-api](https://github.com/envoyproxy/data-plane-api)

The purpose of `sovereign` is to supply downstream envoy proxies with dynamic configuration.


Mechanism of Operation
----------------------
Sovereign allows you to define templates that represent each resource type
provided by Envoy. For example, clusters, routes, listeners, secrets,
extension_configs, etc.

In order to enrich the templates with data, Sovereign has ways of polling data
out-of-band which it then includes as variables that can be accessed within the
templates.

This allows Sovereign to provide configuration to Envoy that changes over time
depending on the data sources, without needing to redeploy the control-plane.

Sovereign provides some built-in ways of polling data (such as over HTTP, or
on-disk) but also exposes extension points, allowing you to write your own
plugins in Python.


Support
------------
[Submit new issues here](https://bitbucket.org/atlassian/sovereign/issues/new)

If you're unable to submit an issue on Bitbucket, send an email to [vsyrakis@atlassian.com](mailto:vsyrakis@atlassian.com)


Release
------------
See [RELEASE.md]


Roadmap
------------
* Performance improvements
* Data persistence
* Push API (versus polling)
* Client for Sovereign
* gRPC


Requirements
------------
* Python 3.8+


Installation
------------
```
pip install sovereign
```

Documentation
-------------
[Read the docs here!](https://developer.atlassian.com/platform/sovereign/)



Local development
=================


Requirements
------------
* Poetry
* Docker
* Docker-compose


Installing dependencies for dev
-------------------------------
Dependencies and creation of virtualenv is handled by poetry
```
poetry install
poetry shell
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


Contributors
============
Pull requests, issues and comments welcome. For pull requests:

* Add tests for new features and bug fixes
* Follow the existing style
* Separate unrelated changes into multiple pull requests

See the existing issues for things to start contributing.

For bigger changes, make sure you start a discussion first by creating
an issue and explaining the intended change.

Atlassian requires contributors to sign a Contributor License Agreement,
known as a CLA. This serves as a record stating that the contributor is
entitled to contribute the code/documentation/translation to the project
and is willing to have it used in distributions and derivative works
(or is willing to transfer ownership).

Prior to accepting your contributions we ask that you please follow the appropriate
link below to digitally sign the CLA. The Corporate CLA is for those who are
contributing as a member of an organization and the individual CLA is for
those contributing as an individual.

* [CLA for corporate contributors](https://na2.docusign.net/Member/PowerFormSigning.aspx?PowerFormId=e1c17c66-ca4d-4aab-a953-2c231af4a20b)
* [CLA for individuals](https://na2.docusign.net/Member/PowerFormSigning.aspx?PowerFormId=3f94fbdc-2fbe-46ac-b14c-5d152700ae5d)


License
========
Copyright (c) 2018 Atlassian and others.
Apache 2.0 licensed, see [LICENSE.txt](LICENSE.txt) file.


