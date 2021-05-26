from typing import Any, Dict
from sovereign.sources.lib import Source
from sovereign.config_loader import Loadable


class File(Source):
    def __init__(self, config: Dict[str, Any], scope: str = "default"):
        super(File, self).__init__(config, scope)
        try:
            self.path = Loadable.from_legacy_fmt(config["path"])
        except KeyError:
            try:
                self.path = Loadable(**config["spec"])
            except KeyError:
                raise KeyError('File source needs to specify "spec" within config')

    def get(self) -> Any:
        """
        Uses the file config loader to load the given path
        """
        return self.path.load()
