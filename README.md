sovereign
=========

Mission statement
-----------------
This project implements a JSON control-plane based on the [envoy](https://envoyproxy.io) [data-plane-api](https://github.com/envoyproxy/data-plane-api)

The purpose of `sovereign` is to supply downstream envoy proxies with 
configuration in near-realtime by responding to discovery requests.

Mechanism of Operation
----------------------
tl;dr version:
```
* Polls HTTP/File/Other for data
* (optional) Applies transforms to the data
* Uses the data to generate Envoy configuration from templates
```

In a nutshell, Sovereign 
gathers contextual data (*"sources"* and *"template context"*), 
optionally applies transforms to that data (using *"modifiers"*) and finally 
uses the data to generate envoy configuration from either python code, or jinja2 templates.

This is performed in a semi-stateless way, where the only state is data cached in memory.

Template context is intended to be statically configured, whereas *Sources* 
are meant to be dynamic - for example, fetching from an API, an S3 bucket, 
or a file that receives updates.

*Modifiers* can mutate the data retrieved from sources, just in case the data 
is in a less than favorable structure.

Both modifiers and sources are pluggable, i.e. it's easy to write your own and 
plug them into Sovereign for your use-case.

Currently, Sovereign supports only providing configuration to Envoy as JSON. 
That is to say, gRPC is not supported yet. Contributions in this area are highly
appreciated!

The JSON configuration can be viewed in real-time with Sovereign's read-only web interface.

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
[Read the docs here!](https://vsyrakis.bitbucket.io/sovereign/docs/)

:new: Read-only user interface
------------------------
Added in `v0.5.3`!

This interface allows you to browse the resources currently returned by Sovereign.

![Sovereign User Interface Screenshot](https://bitbucket.org/atlassian/sovereign/src/master/assets/sovereign_ui.png)

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


