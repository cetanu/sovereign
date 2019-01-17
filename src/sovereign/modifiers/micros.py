"""
Micros modifier
^^^^^^^^^^^^^^^
This modifier is intended to be used within Atlassian!

A short explanation of what this facilitates:

- We have an internal PaaS
- The PaaS lets service owners make their own infrastructure.
- We run an "Open Service Broker" which allows a set of parameters
  to flow through so that people can create their own load-balancing
  on our Envoy proxies.

This modifier will match any data that contains an OSB Plan Id
and then transform it into a format that suits the templates that
we have configured as a default for this project.

To enable this modifier, add the following to your config:

.. code-block:: yaml

   modifiers:
     - micros
"""
from copy import deepcopy
from collections import defaultdict
from sovereign.modifiers.lib import Modifier, GlobalModifier
from sovereign.utils.dictupdate import merge

#: The Plan Id that must be present in the data for this modifier to apply
basic_plan_id = '7d57270a-0348-58d3-829d-447a98fe98d5'


_default_parameters = {
    'upstream_port': 443,
    'upstream_suffix': 'micros-elb',
    'upstream_only': False,
    'healthcheck': 'no',
    'rewrite': 'no',
    'region': 'unknown',
    'domain': list(),
    'routes': list(),
}


def _convert_upstream(region: str, addresses: list, port: int) -> dict:
    for address in addresses:
        yield {
            'address': address['address'],
            'port': address.get('port', port),
            'proto': 'TCP',
            'region': address.get('region', region),
        }


def _cluster(params) -> list:
    if isinstance(params['upstream_address'], str):
        params['upstream_address'] = [params['upstream_address']]
    hosts = list(
        _convert_upstream(
            addresses=params['upstream_address'],
            port=params['upstream_port'],
            region=params['region'],
        )
    )
    return [{
        'name': params['upstream_suffix'],
        'healthchecks': [{'path': params['healthcheck']}],
        'hosts': hosts,
    }]


def _routes(routes: list, default_cluster: str) -> dict:
    for route in routes:
        if 'redirect' in route:
            route['redirect'] = {
                'host_redirect': route['redirect']
            }
        if 'route' in route and 'cluster' not in route['route']:
            route['route']['cluster'] = default_cluster
        yield route


def _virtualhosts(params, service_name) -> list:
    if params['upstream_only']:
        return []
    else:
        return [{
            'name': 'micros-vhost',
            'clusters': [{'name': params['upstream_suffix']}],
            'domains': sorted(set(params['domain'])),
            'rewrite': params['rewrite'],
            'routes': list(_routes(
                routes=params['routes'],
                default_cluster=f'{service_name}-{params["upstream_suffix"]}'
            )),
        }]


class Micros(Modifier):
    def match(self):
        """
        Returns true if the data contains the correct plan id +
        it has not yet been modified (denoted by a field 'translated')
        """
        return self._has_basic_plan and not self._translated

    def apply(self):
        """
        Performs some reshuffling and handling of the data.
        Inserts a new field 'translated' to avoid further modification.
        """
        service_name = self.instance.get('alt_service_name', self.instance['instance_id'])
        binding = self.instance.get('binding_data', {})
        broker_parameters = self.instance['parameters']
        params = deepcopy(_default_parameters)
        params.update(broker_parameters)

        try:
            params['domain'].append(binding['dnsname'])
        except KeyError:
            pass

        self.instance['parameters'] = {
            'clusters': _cluster(params),
            'vhosts': _virtualhosts(params, service_name)
        }
        self.instance['modified'] = True
        return self.instance

    @property
    def _has_basic_plan(self):
        return self.instance.get('plan_id') == basic_plan_id

    @property
    def _translated(self):
        return self.instance.get('modified', False)


class MergeByDomain(GlobalModifier):
    def match(self, data_instance: dict):
        return (
            'alt_service_name' in data_instance and
            'modified' not in data_instance
        )

    def apply(self):
        """
        Instances with the same service name will be combined together
        and will share all domains, clusters, and so on.
        """
        matched = self.matched
        if not matched:
            return

        # Sort by service name AND uuid, to keep order between invocations
        instances = sorted(matched, key=lambda x: (x.get('alt_service_name'), x.get('uuid')))

        # Create buckets of instances with the same service name
        buckets = defaultdict(list)
        for instance in instances:
            service_name = instance['alt_service_name']
            buckets[service_name].append(instance)

        # Merge all the instances within the bucket
        ret = list()
        for _instances in buckets.values():
            final = dict()
            # deep merge every instance in the bucket
            for instance in _instances:
                final = merge(final, instance, merge_lists=True)
            if final != {}:
                ret.append(final)
        self.matched = ret
