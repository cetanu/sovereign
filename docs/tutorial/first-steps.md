# First Steps

## Installation

Ensure you're running at least Python 3.8.0 to get the latest version of Sovereign

```bash
$ python --version
Python 3.8.2
```

If you haven't done so already, you can install Sovereign via pip

```
python -m pip install sovereign
```

## Configuration

The main things you'll need in order to run Sovereign are:

* [Sources](/terminology/#sources)
* [Templates](/terminology/#templates)

Start by creating an somewhat empty YAML configuration file at the location `/etc/sovereign.yaml`

```yaml
sources: []
templates: {}
```

## Config Loaders

Throughout the upcoming documentation you may see paths such as  
`file:///` and `https+json://`.

These are paths that Sovereign uses to dynamically include data in configuration.

The scheme used is generally as follows:
    
    <file_type>+<serialization>://<path>
    
### Types of loaders available

File Type  | Description          | Examples
---------- | -------------------- | -------
file       | Local file           | `file:///absolute_path/file.yaml` <br> `file+json://relative_path/file.json`
env        | Environment Variable | `env://HOSTNAME`
http/https | HTTP location        | `https://domain.com/api/data.yaml` <br> `http+json://domain.com/api/data.json`
module     | Python module path   | `module://package.module:function` <br> `module://ipaddress:IPv4Address`
python     | Raw Python code      | `python:///usr/local/bin/script.py`
pkgdata    | Python Package Data  | `pkgdata+string://sovereign:static/style.css`
s3         | S3 bucket            | `s3://bucketname/filename.yaml` <br> `s3+json://bucketname/filename.json`

### Serializations available

The table above demonstrates the usage of the following serializations

* yaml (default)
* json
* jinja
* string
