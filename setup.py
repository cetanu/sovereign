import os
from setuptools import setup, find_packages

project_name = 'sovereign'

with open('VERSION') as v:
    project_version = v.read()


def requirements():
    try:
        with open('requirements.txt') as f:
            return f.read().splitlines()
    except FileNotFoundError:
        print(os.path.abspath(os.curdir))
        print(os.listdir('.'))
        raise


def readme():
    with open('README.md') as f:
        return f.read()


setup(
    name=project_name,
    version=project_version,
    python_requires='>=3.7.0',
    packages=find_packages('src'),
    package_dir={'': 'src'},
    zip_safe=False,
    include_package_data=True,
    url='https://bitbucket.org/atlassian/sovereign',
    license='Apache-2.0',
    author='Vassilios Syrakis',
    author_email='vsyrakis@atlassian.com',
    description='Envoy Proxy control-plane written in Python',
    long_description=readme(),
    long_description_content_type='text/markdown',
    entry_points={
        "sovereign.sources": [
            "service_broker = sovereign.sources.service_broker:ServiceBroker",
            "file = sovereign.sources.file:File",
            "inline = sovereign.sources.inline:Inline",
        ]
    },
    scripts=[
        'bin/sovereign'
    ],
    install_requires=requirements(),
    command_options={
        'build_sphinx': {
            'project': ('setup.py', project_name),
            'version': ('setup.py', project_version),
            'release': ('setup.py', project_version),
            'source_dir': ('setup.py', 'docs'),
            'config_dir': ('setup.py', 'docs'),
            'build_dir': ('setup.py', 'src/sovereign/docs'),
            'builder': ('setup.py', 'html')
        }
    }
)
