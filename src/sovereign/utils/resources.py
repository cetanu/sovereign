from functools import cache
import importlib.resources as res


@cache
def get_package(name: str):
    return res.files(name)


def get_package_file(package_name: str, filename: str):
    return get_package(package_name).joinpath(filename)


def get_package_file_bytes(package_name: str, filename: str):
    file = get_package_file(package_name, filename)
    return file.read_bytes()
