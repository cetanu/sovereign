from sovereign import cache, config

if not config.worker_v2_enabled:
    reader = cache.CacheReader()
else:
    # don't use the cache reader when in v2 worker mode
    reader = None
