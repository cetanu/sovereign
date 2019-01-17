""" Stolen from the saltstack library """
# pylint: disable=no-name-in-module,too-many-branches
from collections import Mapping
import copy


def update(dest, upd, recursive_update=True, merge_lists=False):
    if (not isinstance(dest, Mapping)) \
            or (not isinstance(upd, Mapping)):
        raise TypeError('Cannot update using non-dict types in dictupdate.update()')
    updkeys = list(upd.keys())
    if not set(list(dest.keys())) & set(updkeys):
        recursive_update = False
    if recursive_update:
        for key in updkeys:
            val = upd[key]
            try:
                dest_subkey = dest.get(key, None)
            except AttributeError:
                dest_subkey = None
            if isinstance(dest_subkey, Mapping) \
                    and isinstance(val, Mapping):
                ret = update(dest_subkey, val, merge_lists=merge_lists)
                dest[key] = ret
            elif isinstance(dest_subkey, list) \
                    and isinstance(val, list):
                if merge_lists:
                    merged = copy.deepcopy(dest_subkey)
                    merged.extend([x for x in val if x not in merged])
                    dest[key] = merged
                else:
                    dest[key] = upd[key]
            else:
                dest[key] = upd[key]
        return dest
    else:
        try:
            for k in upd:
                dest[k] = upd[k]
        except AttributeError:
            # this mapping is not a dict
            for k in upd:
                dest[k] = upd[k]
        return dest


def merge_list(obj_a, obj_b):
    ret = {}
    for key, val in obj_a.items():
        if key in obj_b:
            ret[key] = [val, obj_b[key]]
        else:
            ret[key] = val
    return ret


def merge_recurse(obj_a, obj_b, merge_lists=False):
    copied = copy.deepcopy(obj_a)
    return update(copied, obj_b, merge_lists=merge_lists)


def merge_overwrite(obj_a, obj_b, merge_lists=False):
    for obj in obj_b:
        if obj in obj_a:
            obj_a[obj] = obj_b[obj]
    return merge_recurse(obj_a, obj_b, merge_lists=merge_lists)


def merge(obj_a, obj_b, strategy='recurse', merge_lists=False):
    if strategy == 'list':
        merged = merge_list(obj_a, obj_b)
    elif strategy == 'recurse':
        merged = merge_recurse(obj_a, obj_b, merge_lists)
    elif strategy == 'overwrite':
        merged = merge_overwrite(obj_a, obj_b, merge_lists)
    elif strategy == 'none':
        merged = merge_recurse(obj_a, obj_b)
    else:
        merged = merge_recurse(obj_a, obj_b)

    return merged
