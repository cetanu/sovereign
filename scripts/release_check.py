import re
import sys
import toml


VERSION = re.compile(
    r"(?P<major>\d+)\.(?P<minor>\d+)\.(?P<patch>\d+)(?P<prerelease>a|b|rc)?(?P<number>\d+)?"
)


def is_pre_release():
    with open("pyproject.toml") as f:
        print("Reading pyproject.toml")
        project = toml.load(f)

    version = project["tool"]["poetry"]["version"]
    match_ = VERSION.search(version)
    if match_:
        v = match_.groupdict()
        print(v)
        prerelease = v.get("prerelease")

        if prerelease == "a":
            print("Alpha release")
            return 0
        if prerelease == "b":
            print("Beta release")
            return 0
        if prerelease == "rc":
            print("Release candidate")
            return 0
    return 1


result = is_pre_release()
print(result)
sys.exit(result)
