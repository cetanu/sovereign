from typing import Optional


class DictWithCapacity(dict):
    max_items = 200

    def __init__(self, *args, **kwargs):
        self.max_items = kwargs.pop("max_items", self.max_items)
        super(DictWithCapacity, self).__init__(*args, **kwargs)

    def __setitem__(self, key, val):
        if key not in self:
            max_items = self.max_items - 1
            self._prune(max_items)
        super(DictWithCapacity, self).__setitem__(key, val)

    def update(self, **kwargs):
        super(DictWithCapacity, self).update(**kwargs)
        self._prune(self.max_items)

    def _prune(self, max_items):
        if len(self) >= max_items:
            diff = len(self) - max_items
            for k in list(self.keys())[:diff]:
                del self[k]


def init_store():
    try:
        import redis
        from simplekv.memory.redisstore import RedisStore

        r = redis.StrictRedis(host="redis", port=6379, db=0)
        return RedisStore(r)
    except ImportError:
        from simplekv.memory import DictStore

        return DictStore(d=DictWithCapacity())


def put_resources(node_id: str, resource: str, data: bytes, version: str) -> None:
    data_key = f"{node_id}{resource}"
    version_key = f"{node_id}{resource}version"
    STORE.put(data_key, data)
    STORE.put(version_key, version.encode())


def get_resources(node_id: str, resource: str) -> Optional[bytes]:
    data_key = f"{node_id}{resource}"
    try:
        return STORE.get(data_key)
    except KeyError:
        return None


def version_is_latest(node_id: str, resource: str, version: str) -> bool:
    version_key = f"{node_id}{resource}version"
    try:
        return STORE.get(version_key) == version
    except KeyError:
        return False


STORE = init_store()
