from typing import Optional

try:
    import redis
    from simplekv.memory.redisstore import RedisStore

    r = redis.StrictRedis(host="redis", port=6379, db=0)
    store = RedisStore(r)
except ImportError:
    from simplekv.memory import DictStore

    store = DictStore()


def put_resources(node_id: str, resource: str, data: bytes, version: str) -> None:
    data_key = f"{node_id}{resource}"
    version_key = f"{node_id}{resource}version"
    store.put(data_key, data)
    store.put(version_key, version.encode())


def get_resources(node_id: str, resource: str, version: str) -> Optional[bytes]:
    data_key = f"{node_id}{resource}"
    version_key = f"{node_id}{resource}version"
    try:
        stored_version = store.get(version_key)
        if stored_version == version:
            return None
        return store.get(data_key)
    except KeyError:
        return None


def version_is_latest(node_id: str, resource: str, version: str) -> bool:
    version_key = f"{node_id}{resource}version"
    try:
        return store.get(version_key) == version
    except KeyError:
        return False
