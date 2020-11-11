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
from typing import Callable
from sovereign.statistics import stats
from sovereign.decorators import memoize
from sovereign.schemas import SourceData, Instances, Instance
from sovereign.modifiers.lib import GlobalModifier, Modifier


@memoize(60)
@stats.timed('modifiers.apply_ms')
def modify_sources_in_place(
        source_data: SourceData,
        gmods: Callable[[Instances], GlobalModifier],
        mods: Callable[[Instance], Modifier],
    ) -> SourceData:
    """
    Runs all configured modifiers on received data from sources.
    Returns the data, with modifications applied.
    """
    for scope, instances in source_data.scopes.items():
        for g in gmods:
            global_modifier = g(instances)
            global_modifier.apply()
            source_data.scopes[scope] = global_modifier.join()

        for index, instance in enumerate(source_data.scopes[scope]):
            for m in mods:
                modifier = m(instance)
                if modifier.match():
                    source_data.scopes[scope][index] = modifier.apply()
    return source_data
