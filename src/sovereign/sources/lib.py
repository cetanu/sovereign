"""
Source abstract class
---------------------
This class can be subclassed, installed as an entry point, and then
used via configuration.

`todo entry point install guide`
"""
import abc
from typing import Any, Dict, List


class Source(abc.ABC):
    def __init__(self, config: Dict[str, Any], scope: str) -> None:
        """
        :param config: arbitrary configuration which can be used by the subclass
        """
        self.config = config
        self.scope = scope

    def setup(self) -> None:
        """
        Optional method which is invoked prior to the Source running self.get()
        """
        return None

    @abc.abstractmethod
    def get(self) -> List[Dict[str, Any]]:
        """
        Required method to retrieve data from an arbitrary source
        """
        raise NotImplementedError


class SourceImplementation(Source):
    def __call__(self, config: Dict[str, Any], scope: str) -> "SourceImplementation":
        return self

    def get(self) -> List[Dict[str, Any]]:
        return []
