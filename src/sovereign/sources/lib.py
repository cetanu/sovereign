"""
Source abstract class
---------------------
This class can be subclassed, installed as an entry point, and then
used via configuration.

`todo entry point install guide`
"""
import abc
from sovereign.logs import application_log
from sovereign.schemas import List


class Source(metaclass=abc.ABCMeta):
    def __init__(self, config: dict, scope: str):
        """
        :param config: arbitrary configuration which can be used by the subclass
        """
        self.logger = application_log
        self.config = config
        self.scope = scope

    def setup(self):
        """
        Optional method which is invoked prior to the Source running self.get()
        """

    @abc.abstractmethod
    def get(self) -> List[dict]:
        """
        Required method to retrieve data from an arbitrary source
        """
