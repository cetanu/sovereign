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

## Loadable paths

Throughout the upcoming documentation you may see references to "Loadable paths"

These are paths that Sovereign uses to dynamically include data in configuration.

They are specified in the following way:

```yaml
protocol: <type of loader used>
serialization: <serializer used to decode the data>
path: <location of the data>
```

Most sections that ask you to use a loadable path will provide an example.
    
### Types of loaders available

File Type  | Description          
---------- | -------------------- 
file       | Local file          
env        | Environment Variable 
http/https | HTTP location       
module     | Python module path 
python     | Raw Python code   
pkgdata    | Python Package Data 
s3         | S3 bucket          
inline     | Inline data

### Serializations available

Serializer | Behavior          
---------- | -------------------- 
yaml       | yaml.safe_load(data)
json       | json.loads(data)
orjson     | orjson.loads(data)
ujson      | ujson.loads(data)
jinja      | jinja2.Environment().from_string(data)
jinja2     | jinja2.Environment().from_string(data)
string     | str(data)
raw        | data
