import sys
import toml


def is_pre_release():
    with open("pyproject.toml") as f:
        project = toml.load(f)

    version = project["tool"]["poetry"]["version"]
    _, _, patch = version.split('.')

    prerelease = any((
        patch[0] in ["a", "b"],
        patch[0:1] == "rc"
    ))
    return 0 if prerelease else 1


sys.exit(is_pre_release())
