"""
Source abstract class
---------------------
This class can be subclassed, installed as an entry point, and then
used via configuration.

`todo entry point install guide`
"""
import abc
from sovereign.logs import LOG
from sovereign.schemas import Instances


class Source(metaclass=abc.ABCMeta):
    def __init__(self, config: dict, scope: str):
        """
        :param config: arbitrary configuration which can be used by the subclass
        """
        self.logger = LOG
        self.config = config
        self.scope = scope

    def setup(self):
        """
        Optional method which is invoked prior to the Source running self.get()
        """

    @abc.abstractmethod
    def get(self) -> Instances:
        """
        Required method to retrieve data from an arbitrary source
        """
