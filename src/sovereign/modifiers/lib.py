"""
Modifier abstract class
'''''''''''''''''''''''
This class can be subclassed, installed as an entry point, and then
used via configuration.

`todo entry point install guide`
"""
import abc
from typing import List, Any, Dict


class Modifier(metaclass=abc.ABCMeta):
    """
    Modifier is an abstract base class used to change instances in-flight.

    :param instance: A single instance obtained from any source
    :type instance: dict
    """

    def __init__(self, instance: Dict[str, Any]) -> None:
        self.instance = instance

    @abc.abstractmethod
    def match(self) -> bool:
        """
        match is an abstract method which must be overwritten by all
        inheriting classes.
        This is run prior to applying a modifier, to ensure that it's
        being applied to the correct object.
        Match must return something truthy or falsy.
        """

    @abc.abstractmethod
    def apply(self) -> None:
        """
        apply is an abstract method which must be overwritten by all
        inheriting classes.
        Apply should modify a `self.instance` object in-place.
        """


class GlobalModifier:
    """
    GlobalModifier is an abstract base class used to change instance data in-flight.

    :param source_data: A list of instances obtained from any source
    :type source_data: list
    """

    def __init__(self, source_data: List[Dict[str, Any]]) -> None:
        self.data = source_data
        self.unmatched: List[Dict[str, Any]] = list()
        self.matched: List[Dict[str, Any]] = list()
        self._match()

    @abc.abstractmethod
    def match(self, data_instance: Dict[str, Any]) -> bool:
        """
        match is an abstract method which must be overwritten by all
        inheriting classes.
        This is run prior to applying a global modifier, and results in
        the given data source being sorted into 'matched' and 'unmatched'
        groups.
        Match must return something truthy or falsy.

        :param data_instance: dict object to be matched against
        :return: True if matched, or False if unmatched
        """

    def _match(self) -> None:
        """
        Sorts the given data into two tuples, matched & unmatched, using
        the self.match method
        """
        self.matched = [i for i in self.data if self.match(i)]
        self.unmatched = [i for i in self.data if not self.match(i)]

    @abc.abstractmethod
    def apply(self) -> None:
        """
        apply is an abstract method which must be overwritten by all
        inheriting classes.
        Apply should modify the list object `self.matched` in-place
        """

    def join(self) -> List[Dict[str, Any]]:
        """
        Joins matched and unmatched sets of data back together.
        This is run after the modifier has been applied.
        """
        return self.matched + self.unmatched
