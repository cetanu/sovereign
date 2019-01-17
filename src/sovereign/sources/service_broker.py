"""
Service Broker source
---------------------

Example configuration (YAML):

.. code-block:: yaml

   sources:
     - type: service_broker
       config:
         # List of brokers
         brokers:
           - https://broker1.com/instances
           - https://broker2.net:8443/api/instances

         # Optional: somewhere to keep the last good config
         file: /tmp/broker_result_backup.json

         # Load from debug_instances when requests to brokers fail
         debug: yes
         debug_instances:
           - instance_id: my_service
             parameters:
               upstream_address: service.domain.com
             plan_id: 7d57270a-0348-58d3-829d-447a98fe98d5
             service_id: 10e5a402-45df-5afd-ae86-11377ce2bbb2
             service_clusters:
               - P2
"""
import json
import requests
from requests.exceptions import RequestException
from sovereign import DEBUG
from sovereign.decorators import memoize
from sovereign.sources.lib import Source

USER_AGENT = {
    'User-Agent': 'Envoy-Control-Plane (python-requests/{0})'.format(requests.__version__)
}


class ServiceBroker(Source):
    def __init__(self, *args, **kwargs):
        super(ServiceBroker, self).__init__(*args, **kwargs)
        for arg in args:
            if not isinstance(arg, dict):
                continue
            self.debug = arg.get('debug', DEBUG)
            self.debug_instances = arg.get('debug_instances', [])
            self.file = arg.get('file', './service_broker_instances_backup.json')
            self.brokers = arg.get('brokers', ['http://localhost:5000/v2/service_instances'])

    @staticmethod
    @memoize(30)
    def _get_from_broker(url):
        """
        Cached method that calls a GET to the broker

        :param url: one of the configured broker urls
        :return: HTTP response from the broker
        """
        return requests.get(url, headers=USER_AGENT, timeout=3)

    def get(self) -> list:
        """
        Retrieves data from the broker over http/s

        Returns a last known good configuration in the case of a failure.

        Returns debugging instances given via the service broker source configuration if
        debugging is enabled.

        :return: list of instances from the broker
        """
        request_failed = False
        for url in self.brokers:
            try:
                response = self._get_from_broker(url)
                instance_data = response.json()
            except RequestException:
                request_failed = True
            else:
                self.save(instance_data)
                return instance_data
        if request_failed and self.debug:
            return self.debug_instances
        return self.load()

    def save(self, data):
        """
        Saves a backup of the last known good configuration
        """
        with open(self.file, 'w+') as f:
            json.dump(data, f)

    def load(self):
        """
        Loads the last known good configuration in the case that
        the broker can't be contacted
        """
        with open(self.file) as f:
            return json.load(f)
