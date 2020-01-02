"""
Modifiers
===========
When a request for configuration arrives at the control plane, it will first
retrieve data from all configured sources.

Directly after it has run all sources, it will apply modifications to the data.
If no modifiers are configured, the data is returned as-is.

Modifiers are enabled by adding the following configuration:

.. code-block:: yaml

   modifiers:
     - <modifier_name>

   global_modifiers:
     - <global_modifier_name>

The modifier name must match the name of the entry point

`todo add guide for adding entry points`

Modifiers will apply to each instance of the source data, whereas
global modifiers can apply to the entire set of source data.

Global modifiers are executed before modifiers.
"""
from typing import List
from pkg_resources import iter_entry_points
from sovereign import config
from sovereign.decorators import memoize
from sovereign.statistics import stats


_entry_points = iter_entry_points('sovereign.modifiers')
_modifiers = {ep.name: ep.load()
              for ep in _entry_points
              if ep.name in list(config.modifiers)}

_gentry_points = iter_entry_points('sovereign.global_modifiers')
_gmodifiers = {ep.name: ep.load()
               for ep in _gentry_points
               if ep.name in list(config.global_modifiers)}


@memoize(60)
@stats.timed('modifiers.apply_ms')
def apply_modifications(source_data: List[dict]) -> List[dict]:
    """
    Runs all configured modifiers on received data from sources.
    Returns the data, with modifications applied.
    """
    for g in _gmodifiers.values():
        global_modifier = g(source_data)
        global_modifier.apply()
        source_data = global_modifier.join()

    for index, instance in enumerate(source_data):
        for m in _modifiers.values():
            modifier = m(instance)
            if modifier.match():
                source_data[index] = modifier.apply()
    return source_data
