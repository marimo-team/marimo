# Copyright 2024 Marimo. All rights reserved.
"""Flatten and repack nested structures of lists, tuples, and dicts

Adapted from https://github.com/ericmjl/pyflatten/tree/master; changed
to handle generic leaf data types and minimize recursion stack depth.

TODO(akshayka): if this becomes a bottleneck, use a library like dm-tree
(this implementation will be slow large structures); as of writing,
installation of dm-tree on macOS is buggy
"""

from __future__ import annotations

import itertools
from typing import Any, Callable, Dict, List, Tuple, Type, Union

STRUCT_TYPE = Union[Tuple[Any, ...], List[Any], Dict[Any, Any]]
UNFLATTEN_TYPE = Callable[[List[Any]], Union[STRUCT_TYPE, Any]]
FLATTEN_RET_TYPE = Tuple[List[Any], UNFLATTEN_TYPE]


class CyclicStructureError(Exception):
    pass


def _is_leaf(obj: Any) -> bool:
    return not isinstance(obj, (list, tuple, dict))


def _flatten_sequence(
    value: list[Any] | tuple[Any, ...], json_compat_keys: bool, seen: set[int]
) -> FLATTEN_RET_TYPE:
    """Flatten a sequence of values"""
    base_type: Type[List[Any]] | Type[Tuple[Any, ...]]
    if isinstance(value, list):
        base_type = list
    elif isinstance(value, tuple):
        base_type = tuple
    else:
        raise ValueError("value is not a list or tuple: ", value)

    # Algorithm:
    #
    # Accumulate a list of flattened pieces and unflattener functions,
    # one for each chunk of value.
    #
    # A chunk is one of the following:
    #  1 a sequence (possibly empty) of leaves
    #  2 a nested structure
    #
    # Chunks of type 1 are a base case
    # Chunks of type 2 are recursed on using flatten
    #
    # Implementing chunks of type 1 as a base case significantly decreases
    # the recursion stack depth compared to the reference implementation
    if not value:
        # unflattener returns an empty tuple or empty list
        return [], lambda _: base_type()

    lengths = []
    flattened_pieces: list[list[Any]] = []
    unflatteners: list[UNFLATTEN_TYPE] = []
    i = 0
    while i < len(value):
        if _is_leaf(value[i]):
            # process a chunk of type 1: a sequence of leaves
            lengths.append(0)
            flattened_pieces.append([])
            while i < len(value) and _is_leaf(value[i]):
                flattened_pieces[-1].append(value[i])
                lengths[-1] += 1
                i += 1
            unflatteners.append(lambda x: x)
        # if we haven't exhausted the sequence, then we've hit a value that
        # is not a leaf
        if i < len(value):
            assert not _is_leaf(value[i])
            flattened, u = _flatten(value[i], json_compat_keys, seen)
            lengths.append(len(flattened))
            flattened_pieces.append(flattened)

            # u=u forces Python to bind the unflattener function u
            # to the lambda; without that (if u were just closed
            # over) every element of unflatteners would point to the last
            # u because of Python's late-binding
            def uprime(v: list[Any], u: UNFLATTEN_TYPE = u) -> STRUCT_TYPE:
                return [u(v)]

            unflatteners.append(uprime)
        i += 1

    def unflatten(vector: list[Any]) -> STRUCT_TYPE:
        unflattened_pieces = []
        pointer = 0
        # How unflattening works
        #
        # consecutive leaves (e.g., 1, 2) are unflattened as
        #   [leaves ...] ([1, 2])
        #
        # non-leaves (e.g., {1: 2}, or [1, 2]) are unflattened as
        #  [[structure]] ([{1: 2}] or [[1, 2]])
        #
        # we chain the unflattened pieces together to pack them according to
        # the structure of value
        for unflattener, length in zip(unflatteners, lengths):
            unflattened_pieces.append(
                unflattener(vector[pointer : pointer + length])
            )
            pointer += length
        if isinstance(value, tuple):
            return tuple(itertools.chain(*unflattened_pieces))
        elif isinstance(value, list):
            return list(itertools.chain(*unflattened_pieces))
        else:
            raise ValueError("Invalid type of value ", type(value))

    return (
        list(itertools.chain(*flattened_pieces)),
        unflatten,
    )


def _flatten(
    value: Any, json_compat_keys: bool, seen: set[int]
) -> FLATTEN_RET_TYPE:
    # Track ids of structures to make sure that the tree has a finite height,
    # ie, to make sure that no structure contains itself.
    value_id = id(value)
    if isinstance(value, (tuple, list, dict)):
        if value_id in seen:
            raise CyclicStructureError("already seen ", value)

    if isinstance(value, (tuple, list)):
        seen.add(value_id)
        ret = _flatten_sequence(value, json_compat_keys, seen)
        seen.remove(value_id)
        return ret
    elif isinstance(value, dict):
        if not value:
            return [], lambda _: {}

        seen.add(value_id)
        flattened = []
        unflatteners = []
        lengths = []
        keys = []
        for k, v in value.items():
            curr_flattened, curr_unflatten = _flatten(
                v, json_compat_keys, seen
            )
            flattened.append(curr_flattened)
            unflatteners.append(curr_unflatten)
            lengths.append(len(curr_flattened))
            if json_compat_keys and not (
                isinstance(k, (str, int, float, bool)) or k is None
            ):
                keys.append(str(k))
            else:
                keys.append(k)
        seen.remove(value_id)

        def unflatten(vector: list[Any]) -> STRUCT_TYPE:
            pointer = 0
            d = {}
            for key, unflattener, length in zip(keys, unflatteners, lengths):
                piece = vector[pointer : pointer + length]
                d[key] = unflattener(piece)
                pointer += length
            return d

        return list(itertools.chain(*flattened)), unflatten
    else:
        return [value], lambda x: x[0]


def flatten(value: Any, json_compat_keys: bool = False) -> FLATTEN_RET_TYPE:
    """Flatten a nested structure.

    Returns the structure flattened and a repacking function.

    Replacing function expects a flat list of the same length as
    the flattened structure.

    Usage:

    ```python
    value = [1, [2, 3], {"4": [5, 6]}, []]
    flattened, unflattener = flatten(value)
    # apply a map or other processing to each value of flattened ...
    # ...
    # packed_as_value has same nesting structure as value
    packed_as_value = unflattener(processed_flattened)
    ```

    Args:
    ----
    value: nested structure of lists, tuples, and dicts
    json_compat_keys: if True, unflattener will stringify dict keys when
      keys are not JSON compatible

    Returns:
    -------
    flattened_value, unflattener function

    Raises:
    ------
    CyclicStructureError: If the structure has a cyclic nesting pattern,
        such as a list that contains itself
    """
    flattened, u = _flatten(value, json_compat_keys, seen=set())

    def unflatten_with_validation(vector: list[Any]) -> STRUCT_TYPE:
        if type(vector) != list:  # noqa: E721
            raise ValueError(
                "unflatten function requires a list as input, "
                + f" but got {type(list)}"
            )
        elif len(vector) != len(flattened):
            raise ValueError(
                f"Length of unflatten's input must be {len(flattened)}, "
                + f"but got {len(vector)}"
            )
        return u(vector)

    return flattened, unflatten_with_validation


def contains_instance(value: Any, instance: Any) -> bool:
    """
    Recursively checks if value contains the given instance
    """

    seen: set[int] = set()

    def _contains_instance(value: Any) -> bool:
        if id(value) in seen:
            return False
        seen.add(id(value))

        if isinstance(value, (tuple, list)):
            return any(_contains_instance(v) for v in value)
        elif isinstance(value, dict):
            return any(_contains_instance(v) for v in value.values())
        else:
            return isinstance(value, instance)

    return _contains_instance(value)
