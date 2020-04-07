# Modifiers

## What are modifiers?

As explained a little bit in [Terminology](/terminology/#modifiers),
modifiers are a sort of plugin system.

Modifiers are Python modules that can be configured to 
run while Sovereign is in operation, to transform Instances in some way.

There are two types of modifiers:

* **Modifier:** applies some action to each instance
* **Global Modifier:** applies some action to the entire set of instances, per [scope](/terminology/#scopes).

## Why/when should they be used?

In general, modifiers should be used when you need to change the data from your [Sources](/terminology/#sources) in some way
before it is used to generate Envoy configuration with [Templates](/terminology/#templates)

Maybe your data requires additional validation, transformation, or some other complex
operation that would be too messy in template code.

Or maybe the data from your Sources is user-friendly, but you need 
to convert this into something more structured.

!!! tip

    Modifiers run in the same background thread that fetches Sources, which means
    that they do not impact the performance of discovery requests, and have no cost
    when it comes to generating envoy configuration from templates.

## Creating and installing a Modifier

Modifiers are installed using entry points in Python.

The following steps give a contrived example of how you would create and install a modifier into Sovereign using entry points.

---

# **Tutorial:** The Foobar Injector

The following tutorial will guide you through the creation of a Modifier which adds a 
key:value pair `{"foo": "bar"}` to every instance that matches certain conditions.

For this short tutorial, let's imagine that we have configured [the inline sources from the tutorial](/tutorial/sources/#using-multiple-sources),
so that we have some instances to work with.

### Create a Python module

First, create an empty Python module.

For this example the following folder structure will be used:

```text
├───my_custom_modifier
    ├───__init__.py   # <- This file is left empty
    └───foobar.py
├───setup.py
└───sovereign.yaml
```

!!! tip
    
    You'll notice a `sovereign.yaml` file in the above folder structure.
    
    It's expected that modifiers are stored and installed in the same directory as your configuration.  
    However, this is not strictly required, and you can install a modifier from anywhere on the filesystem,
    as long as it is installed with the same Python runtime which is going to run Sovereign.

### Add a Modifier to the module

Sovereign provides a Modifier class which has some methods that must be implemented.  

```python
# my_custom_modifier/foobar.py
from sovereign.modifiers.lib import Modifier


class AddFooBar(Modifier):
    """
    Adds a key:value "foo":"bar" to each instance
    """

    def match(self):
        """
        In order for the Modifier to apply to an instance,
        this function must return True.
        """
        return self.instance.get('group') == 'A'

    def apply(self):
        """
        If `match` returned True, this function is called.
        
        Perform modifications to self.instance and then return it
        """

        # Add {"foo": "bar"} to the instance.
        self.instance['foo'] = 'bar'
        return self.instance
```

This modifier, when executed, should only apply to the first instance, since the match
condition is that the instance has a key `group` with a value of `A`.

### Write a setuptools script

The following script adds your Python module to the list of modifiers, which
Sovereign checks at runtime:

```python
from setuptools import setup, find_packages

setup(
    name='my_custom_modifier',
    packages=find_packages(),
    entry_points={
        "sovereign.modifiers": [
            "foobar_injector = my_custom_modifier.foobar:AddFooBar",
        ]
    }
)
```

This will install the above Python module into an entry point named `sovereign.modifiers`,
with a name of `foobar_injector`

### Install the Python module in the same place that you installed Sovereign

You'll need to run the above setup script wherever you've installed Sovereign, using `pip install sovereign` or similar.

Simply run `python setup.py install` and you should see output similar to the following:

```bash hl_lines="33"
$ python setup.py install
running install
running bdist_egg
running egg_info
writing my_custom_modifier.egg-info\PKG-INFO
writing dependency_links to my_custom_modifier.egg-info\dependency_links.txt
writing entry points to my_custom_modifier.egg-info\entry_points.txt
writing top-level names to my_custom_modifier.egg-info\top_level.txt
reading manifest file 'my_custom_modifier.egg-info\SOURCES.txt'
writing manifest file 'my_custom_modifier.egg-info\SOURCES.txt'
installing library code to build\bdist.win32\egg
running install_lib
running build_py
creating build\bdist.win32\egg
creating build\bdist.win32\egg\my_custom_modifier
copying build\lib\my_custom_modifier\foobar.py -> build\bdist.win32\egg\my_custom_modifier
copying build\lib\my_custom_modifier\__init__.py -> build\bdist.win32\egg\my_custom_modifier
byte-compiling build\bdist.win32\egg\my_custom_modifier\foobar.py to foobar.cpython-38.pyc
byte-compiling build\bdist.win32\egg\my_custom_modifier\__init__.py to __init__.cpython-38.pyc
creating build\bdist.win32\egg\EGG-INFO
copying my_custom_modifier.egg-info\PKG-INFO -> build\bdist.win32\egg\EGG-INFO
copying my_custom_modifier.egg-info\SOURCES.txt -> build\bdist.win32\egg\EGG-INFO
copying my_custom_modifier.egg-info\dependency_links.txt -> build\bdist.win32\egg\EGG-INFO
copying my_custom_modifier.egg-info\entry_points.txt -> build\bdist.win32\egg\EGG-INFO
copying my_custom_modifier.egg-info\top_level.txt -> build\bdist.win32\egg\EGG-INFO
zip_safe flag not set; analyzing archive contents...
creating 'dist\my_custom_modifier-0.0.0-py3.8.egg' and adding 'build\bdist.win32\egg' to it
removing 'build\bdist.win32\egg' (and everything under it)
Processing my_custom_modifier-0.0.0-py3.8.egg
Copying my_custom_modifier-0.0.0-py3.8.egg to .....\lib\site-packages
Adding my-custom-modifier 0.0.0 to easy-install.pth file

Installed .....\lib\site-packages\my_custom_modifier-0.0.0-py3.8.egg
Processing dependencies for my-custom-modifier==0.0.0
Finished processing dependencies for my-custom-modifier==0.0.0
```

### Configuring Sovereign to use the Modifier

Sovereign will execute any modifiers added to its main configuration

```yaml
# /etc/sovereign.yaml
modifiers:
  - foobar_injector
```

The minimum working example (again, using the sources from the tutorial) would be the following:

```yaml
modifiers:
  - foobar_injector

sources: 
  - type: inline
    config:
      instances:
        - name: instance-A-01
          address: 10.0.0.50
          group: A
          id: '01'
  - type: inline
    config:
      instances:
        - name: instance-B-01
          address: 10.100.24.10
          group: B
          id: '01'

templates:
  default: {}
```
    
### Verifying the behavior

Once Sovereign is running, you can see that it modified the first instance but left the second one unchanged.

There is a debugging endpoint available: `/admin/source_dump`.  
This accepts a query parameter, `modified` (default is `yes`) so that you can see the instances before and after being modified.

```bash hl_lines="8"
$ curl localhost:8000/admin/source_dump?modified=yes | jq
[
  {
    "name": "instance-A-01",
    "address": "10.0.0.50",
    "group": "A",
    "id": "01",
    "foo": "bar"
  },
  {
    "name": "instance-B-01",
    "address": "10.100.24.10",
    "group": "B",
    "id": "01"
  }
]

```

### Recap

* We created a Python module, containing an object that inherits from Modifier from the Sovereign library
* We added logic that performs a `match`, and then an `apply` which performs some action on matched instances
* We made a setup script, and installed it to the same machine which has Sovereign installed
* We added the `foobar_injector` to the list of modifiers, therefore informing Sovereign to execute it
* We verified that the modifier applied to the correct instance(s) using the `/admin/source_dump` debugging endpoint
