# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import json
import sys
from collections import defaultdict
from typing import TYPE_CHECKING, Any

from marimo._messaging.mimetypes import KnownMimeType
from marimo._output import formatting
from marimo._output.data.data import is_bigint
from marimo._output.formatters.formatter_factory import FormatterFactory
from marimo._output.formatters.repr_formatters import maybe_get_repr_formatter
from marimo._plugins.stateless.inspect import inspect
from marimo._plugins.stateless.plain_text import plain_text
from marimo._utils.flatten import CyclicStructureError, flatten

if TYPE_CHECKING:
    from collections.abc import Sequence


def is_structures_formatter(
    formatter: formatting.Formatter[object] | None,
) -> bool:
    return formatter is formatting.get_formatter(())


_KEY_STR_PREFIX = "text/plain+"
_KEY_STR_ESCAPE = "text/plain+str:"


def _key_formatter(k: object) -> object:
    """Encode a dict key so it survives a JSON round-trip without colliding.

    JSON object keys are always strings, so a Python dict key that is a
    non-string primitive (e.g. `2`, `True`) stringifies to something that
    can collide with an equal-looking `str` key (`"2"`, `"true"`) — and
    `JSON.parse` on the frontend silently drops duplicates.

    Non-string keys are encoded with a mimetype prefix so the frontend
    renderer can restore the original type. String keys that happen to
    start with our prefix are escaped so they round-trip unchanged.
    """
    # bool is an int subclass in Python; check it first.
    if isinstance(k, bool):
        return f"text/plain+bool:{k}"
    if isinstance(k, str):
        if k.startswith(_KEY_STR_PREFIX):
            return f"{_KEY_STR_ESCAPE}{k}"
        return k
    if k is None:
        return "text/plain+none:"
    if isinstance(k, int):
        # No bigint/int split for keys: the numeric payload lives inside
        # a string, so there's no JS `Number` precision concern.
        return f"text/plain+int:{k}"
    if isinstance(k, float):
        # Cover the JSON-spec-violating NaN/Inf cases; json.dumps would
        # emit bare `NaN`/`Infinity` which `JSON.parse` rejects.
        import math

        if math.isnan(k):
            return "text/plain+float:nan"
        if math.isinf(k):
            return "text/plain+float:inf" if k > 0 else "text/plain+float:-inf"
        return f"text/plain+float:{k}"
    if isinstance(k, tuple):
        try:
            return f"text/plain+tuple:{json.dumps(list(k))}"
        except TypeError:
            return _escape_fallback(str(k))
    if isinstance(k, frozenset):
        try:
            return f"text/plain+frozenset:{json.dumps(list(k))}"
        except TypeError:
            return _escape_fallback(str(k))
    return _escape_fallback(str(k))


def _escape_fallback(s: str) -> str:
    """Prevent a stringified fallback key from decoding as a typed key.

    The fallback path runs `str(k)` on unusual key types (non-JSON-safe
    tuple contents, custom hashables, etc.). If that happens to produce
    a string starting with `text/plain+`, the frontend would decode it
    as a typed key. Apply the same escape we use for literal string keys.
    """
    if s.startswith(_KEY_STR_PREFIX):
        return f"{_KEY_STR_ESCAPE}{s}"
    return s


def _leaf_formatter(
    value: object,
) -> bool | None | str | int:
    formatter = formatting.get_formatter(value)

    # Because we don't flatten subclasses of structures, we need to avoid
    # recursing on structures in order to prevent infinite recursion.
    if formatter is not None and not is_structures_formatter(formatter):
        return ":".join(formatter(value))

    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value
    if isinstance(value, int):
        if is_bigint(value):
            return f"text/plain+bigint:{value}"
        return value
    # floats are still converted to strings because JavaScript
    # can't reliably distinguish between them (eg 1 and 1.0)
    if isinstance(value, float):
        return f"text/plain+float:{value}"
    if value is None:
        return value
    if isinstance(value, frozenset):
        # Separate branch from `set` so the frontend can emit the right
        # literal — `{1, 2}` for set, `frozenset({1, 2})` for frozenset,
        # and `set()` / `frozenset()` for the empty cases.
        try:
            return f"text/plain+frozenset:{json.dumps(list(value))}"
        except TypeError:
            return f"text/plain:{value}"
    if isinstance(value, set):
        # Emit a JSON-list payload so the frontend uses the same
        # double-quoted element rendering as every other encoded type
        # (tuples, frozensets as keys, etc.). Falls back to Python's
        # `str()` form for sets containing non-JSON-safe elements.
        try:
            return f"text/plain+set:{json.dumps(list(value))}"
        except TypeError:
            return f"text/plain+set:{value!s}"
    if isinstance(value, tuple):
        return f"text/plain+tuple:{json.dumps(value)}"

    try:
        return f"text/plain:{json.dumps(value)}"
    except TypeError:
        return f"text/plain:{value}"


def format_structure(
    t: tuple[Any, ...] | list[Any] | dict[str, Any],
) -> tuple[Any, ...] | list[Any] | dict[str, Any]:
    """Format the leaves of a structure.

    Returns a structure of the same shape as `t` with formatted
    leaves.
    """
    flattened, repacker = flatten(
        t,
        json_compat_keys=True,
        flatten_formattable_subclasses=False,
        key_formatter=_key_formatter,
    )
    return repacker([_leaf_formatter(v) for v in flattened])


def _collect_dict_artists(
    t: dict[str, Any],
    artist_type: type,
) -> list[Any]:
    """Collect matplotlib Artists from dict values (e.g. boxplot/violinplot).

    Returns a flat list of artists, or an empty list if any value is not
    an Artist or collection of Artists.
    """
    artists: list[Any] = []
    for v in t.values():
        if isinstance(v, (list, tuple)):
            if not all(isinstance(item, artist_type) for item in v):
                return []
            artists.extend(v)
        elif isinstance(v, artist_type):
            artists.append(v)
        else:
            return []
    return artists


def _format_single_figure(
    artists: Sequence[Any],
) -> tuple[KnownMimeType, str] | None:
    """If all artists share the same figure, format that figure."""
    figs = [getattr(a, "figure", None) for a in artists]
    if all(f is not None and f == figs[0] for f in figs):
        fig_formatter = formatting.get_formatter(figs[0])
        if fig_formatter is not None:
            return fig_formatter(figs[0])
    return None


class StructuresFormatter(FormatterFactory):
    @staticmethod
    def package_name() -> None:
        return None

    def register(self) -> None:
        @formatting.formatter(list)
        @formatting.formatter(tuple)
        @formatting.formatter(dict)
        @formatting.formatter(defaultdict)
        def _format_structure(
            t: tuple[Any, ...]
            | list[Any]
            | dict[str, Any]
            | defaultdict[Any, Any],
        ) -> tuple[KnownMimeType, str]:
            # Some objects extend list/tuple/dict, but also have _repr_ methods
            # that we want to use preferentially.
            repr_formatter = maybe_get_repr_formatter(t)
            if repr_formatter is not None:
                return repr_formatter(t)

            # Check if the object is a subclass of tuple, list, or dict
            # and the repr is different from the default
            # e.g. sys.version_info
            if isinstance(t, tuple) and type(t) is not tuple:
                if str(t) != str(tuple(t)):
                    return plain_text(str(t))._mime_()
            elif isinstance(t, list) and type(t) is not list:
                if str(t) != str(list(t)):
                    return plain_text(str(t))._mime_()
            elif (
                isinstance(t, dict)
                and type(t) is not dict
                and type(t) is not defaultdict
            ):
                if str(t) != str(dict(t)):
                    return plain_text(str(t))._mime_()
            elif isinstance(t, defaultdict) and type(t) is not defaultdict:
                if str(t) != str(defaultdict(t.default_factory, t)):
                    return plain_text(str(t))._mime_()

            if t and "matplotlib" in sys.modules:
                # Special case for matplotlib:
                #
                # plt.plot() returns a list of lines 2D objects, one for each
                # line, which typically have identical figures. Without this
                # special case, if a plot had (say) 5 lines, it would be shown
                # 5 times.
                #
                # ax.boxplot()/violinplot() return dicts with artist values.
                #
                # These special cases won't work if a plot is in a nested
                # structure. We could be more opinionated and recurse, but
                # in most cases the recursion will be a performance hit with no
                # benefit, so this is probably fine as is.
                import matplotlib.artist  # type: ignore

                artist_type = matplotlib.artist.Artist
                result = None
                if isinstance(t, dict):
                    artists = _collect_dict_artists(t, artist_type)
                    if artists:
                        result = _format_single_figure(artists)
                elif all(isinstance(i, artist_type) for i in t):
                    result = _format_single_figure(t)

                if result is not None:
                    return result
            try:
                formatted_structure = format_structure(t)
            except CyclicStructureError:
                return ("text/plain", str(t))

            return ("application/json", json.dumps(formatted_structure))

        import types

        @formatting.formatter(types.BuiltinFunctionType)
        @formatting.formatter(types.BuiltinMethodType)
        @formatting.formatter(types.FunctionType)
        @formatting.formatter(types.LambdaType)
        @formatting.formatter(types.MethodType)
        def _format_function(obj: Any) -> tuple[KnownMimeType, str]:
            try:
                # If the function has a repr_formatter, use it
                repr_formatter = maybe_get_repr_formatter(obj)
                if repr_formatter is not None:
                    return repr_formatter(obj)
                # Otherwise, use the pretty inspect
                return inspect(obj, value=False)._mime_()
            except Exception:
                # If it fails, fallback to just 'repr'
                return plain_text(repr(obj))._mime_()
