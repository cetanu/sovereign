import os
from setuptools import setup, find_packages


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
    name='sovereign',
    version='0.1.10',
    python_requires='>=3.6.0',
    packages=find_packages('src'),
    package_dir={'': 'src'},
    package_data={
        'src/sovereign': ['docs/*', ]
    },
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
        ],
        "sovereign.modifiers": [
            "micros = sovereign.modifiers.micros:Micros",
        ],
        "sovereign.global_modifiers": [
            "merge_by_domain = sovereign.modifiers.micros:MergeByDomain"
        ]
    },
    scripts=[
        'bin/sovereign'
    ],
    install_requires=requirements(),
)
