from functools import cache
import importlib.resources as res
from importlib.resources.abc import Traversable


@cache
def get_package(name: str) -> Traversable:
    return res.files(name)


def get_package_file(package_name: str, filename: str) -> Traversable:
    return get_package(package_name).joinpath(filename)


def get_package_file_bytes(package_name: str, filename: str) -> bytes:
    file = get_package_file(package_name, filename)
    return file.read_bytes()
