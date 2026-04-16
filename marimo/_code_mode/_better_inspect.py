# Copyright 2026 Marimo. All rights reserved.
"""better_inspect -- opinionated replacements for dir() and help().

Why these exist:
Python's built-in dir() and help() were designed in a pre-AI, pre-LSP era.
They dump too much noise (dunders, inherited object methods, pager UIs) and
produce output that's hard to scan, hard to copy-paste into prompts, and hard
to feed to tools.

These two functions fix that:

``better_dir(obj)``
    Filters out all private/dunder attributes.
    Appends type annotations to data attributes (e.g. ``host: str``).
    Appends full signatures to callables (e.g. ``send(data: bytes) -> int``).
    Returns a plain ``list[str]`` so it's a drop-in ``__dir__`` return value.
    Uses ``object.__dir__(obj)`` internally to avoid infinite recursion
    when wired as ``__dir__``.

``better_help(obj)``
    Returns a compact, markdown-ish summary: class name, docstring,
    attributes with types, methods with signatures and one-line docs.
    No pager, no dunders, no self parameter, no scroll.
    Returns ``str`` so it can be wired to ``__repr__`` and will also be
    picked up by ``help()`` via pydoc's repr fallback.

``@helpable``
    Class decorator that rewrites ``__doc__`` at definition time so
    ``help()`` shows the clean summary natively via pydoc -- no need to
    touch ``__repr__``. Also wires ``__dir__`` automatically.

Usage::

    from marimo._code_mode._better_inspect import better_dir, better_help, helpable

    # Standalone
    better_dir(my_obj)
    better_help(my_obj)

    # Zero-boilerplate via decorator
    @helpable
    class MyClient:
        \"\"\"A TCP client for sending data to a remote server.\"\"\"

        def __init__(self, host: str, port: int = 8080):
            self.host = host
            self.port = port

        def connect(self, timeout: float = 5.0) -> bool:
            \"\"\"Connect to the remote server.\"\"\"
            ...

        def send(self, data: bytes, timeout: float = 5.0) -> int:
            \"\"\"Send data to the server.\"\"\"
            ...

        def disconnect(self) -> None:
            \"\"\"Disconnect from the server.\"\"\"
            ...

    # Now both work natively:
    #   dir(client)   -> clean list with types and signatures
    #   help(client)  -> pydoc shows the clean summary via __doc__
"""

from __future__ import annotations

import inspect
from enum import Enum, EnumMeta
from typing import Any


def _public_attrs(obj: Any) -> list[str]:
    """Return sorted public attribute names using ``object.__dir__``.

    Uses ``object.__dir__(obj)`` instead of ``dir(obj)`` to avoid infinite
    recursion when this is called from inside ``__dir__`` itself.

    Args:
        obj: Any Python object.

    Returns:
        Sorted list of attribute names that don't start with ``_``.
    """
    # Enum classes: only show member names.
    if isinstance(obj, type) and issubclass(obj, Enum):
        return sorted(m.name for m in obj)
    # For classes (types), use type.__dir__ to get the class's own attributes.
    # For instances, use object.__dir__ to avoid recursion through __dir__.
    raw = type.__dir__(obj) if isinstance(obj, type) else object.__dir__(obj)
    return sorted(name for name in raw if not name.startswith("_"))


_MISSING: Any = object()


def _safe_getattr_static(obj: Any, name: str) -> Any:
    """Fetch an attribute without invoking descriptors or properties.

    Uses ``inspect.getattr_static`` so that ``dir()``/``help()`` never
    trigger property getters (which could raise or have side effects).
    Returns ``_MISSING`` if the attribute cannot be retrieved.
    """
    try:
        return inspect.getattr_static(obj, name)
    except AttributeError:
        return _MISSING


def _type_label(val: Any) -> str:
    """Best-effort type label for a value.

    For property descriptors (seen when inspecting a class rather than an
    instance), extracts the return annotation from the getter.
    """
    if isinstance(val, property) and val.fget is not None:
        ret = getattr(val.fget, "__annotations__", {}).get("return")
        if ret is not None:
            return ret.__name__ if isinstance(ret, type) else str(ret)
    return type(val).__name__


def _unwrap_callable(val: Any) -> Any:
    """Unwrap ``classmethod``/``staticmethod`` to the underlying function."""
    if isinstance(val, (classmethod, staticmethod)):
        return val.__func__
    return val


def _format_signature(func: Any) -> str:
    """Return a string signature with ``self``/``cls`` stripped."""
    sig = inspect.signature(func)
    params = [p for n, p in sig.parameters.items() if n not in ("self", "cls")]
    return str(sig.replace(parameters=params))


def _first_doc_line(doc: str | None) -> str:
    if not doc:
        return ""
    return doc.strip().split("\n", 1)[0]


def better_dir(obj: Any) -> list[str]:
    """A cleaner ``dir()`` that shows only the public interface.

    Designed to be returned directly from ``__dir__``::

        def __dir__(self):
            return better_dir(self)

    Improvements over built-in ``dir()``:

    - Excludes all private and dunder attributes.
    - Data attributes show their type       -> ``host: str``
    - Callables show their full signature   -> ``send(data: bytes) -> int``
    - Sorted alphabetically for easy scanning.
    - Returns ``list[str]`` -- the exact type ``__dir__`` requires.
    - Safe from infinite recursion (uses ``object.__dir__`` internally).

    Args:
        obj: Any Python object (instance, class, module, ...).

    Returns:
        A sorted list of formatted public attribute descriptions.

    Example::

        >>> better_dir(my_client)
        ['connect(timeout: float = 5.0) -> bool',
         'disconnect() -> None',
         'host: str',
         'port: int',
         'send(data: bytes, timeout: float = 5.0) -> int']
    """
    result: list[str] = []

    for name in _public_attrs(obj):
        val = _safe_getattr_static(obj, name)
        if val is _MISSING:
            continue

        call_target = _unwrap_callable(val)

        if isinstance(val, property):
            result.append(f"{name}: {_type_label(val)}")
        elif isinstance(val, Enum):
            result.append(f"{name} = {val.value!r}")
        elif callable(call_target):
            try:
                sig = _format_signature(call_target)
            except (ValueError, TypeError):
                sig = "(...)"
            result.append(f"{name}{sig}")
        else:
            result.append(f"{name}: {_type_label(val)}")

    return result


def better_help(obj: Any) -> str:
    """A compact, AI-friendly replacement for ``help()``.

    Can be used standalone, or applied automatically via the ``@helpable``
    decorator which rewrites ``__doc__`` at class definition time so that
    ``help()`` shows this output natively through pydoc.

    Improvements over built-in ``help()``:

    - Markdown-style heading with the class/module name.
    - Shows only the first line of each docstring -- enough to understand
      intent without the filler.
    - ``self`` is stripped from method signatures by ``inspect.signature``.
    - Attributes and methods are grouped into clearly labelled sections.
    - No pager, no quitting, no scrolling -- just a string.
    - Output is structured for LLMs: paste it straight into a prompt,
      a README, or a tool description.
    - Returns ``str`` instead of printing, so it composes cleanly with
      logging, f-strings, ``__repr__``, etc.

    Args:
        obj: Any Python object (instance, class, module, ...).

    Returns:
        A formatted multi-line string describing the object's public interface.

    Example::

        >>> print(better_help(my_client))
        # MyClient
        A TCP client for sending data to a remote server.

    Attributes:
          host: str
          port: int

    Methods:
          connect(timeout: float = 5.0) -> bool  -- Connect to the remote server.
          disconnect() -> None  -- Disconnect from the server.
          send(data: bytes, timeout: float = 5.0) -> int  -- Send data to the server.
    """
    # Pick a reasonable title for any object kind (modules, functions, ...).
    title = getattr(obj, "__name__", None) or type(obj).__name__

    lines: list[str] = [f"# {title}"]

    # Prefer the original (pre-@helpable) docstring so we don't duplicate
    # the generated heading or drop the human-written description line.
    raw_doc = getattr(obj, "_original_doc__", None) or getattr(
        obj, "__doc__", None
    )
    desc = _first_doc_line(raw_doc)
    # Strip the generated `# Name` heading if _original_doc__ is unavailable.
    if desc.startswith("#"):
        desc = ""
    if desc:
        lines.append(desc)

    lines.append("")

    attrs: list[str] = []
    methods: list[str] = []

    for name in _public_attrs(obj):
        val = _safe_getattr_static(obj, name)
        if val is _MISSING:
            continue

        call_target = _unwrap_callable(val)

        if isinstance(val, property):
            attrs.append(f"  {name}: {_type_label(val)}")
            continue

        if callable(call_target) and not isinstance(val, Enum):
            try:
                sig = _format_signature(call_target)
            except (ValueError, TypeError):
                sig = "(...)"
            doc = _first_doc_line(getattr(call_target, "__doc__", None))
            entry = f"  {name}{sig}"
            if doc:
                entry += f"  -- {doc}"
            methods.append(entry)
        elif isinstance(val, Enum):
            attrs.append(f"  {name} = {val.value!r}")
        else:
            attrs.append(f"  {name}: {_type_label(val)}")

    if attrs:
        lines.append("Attributes:")
        lines.extend(attrs)
        lines.append("")

    if methods:
        lines.append("Methods:")
        lines.extend(methods)

    return "\n".join(lines)


def _build_enum_help(cls: type) -> str:
    """Build help for an Enum class, showing members with values and docs."""
    original_doc: str | None = getattr(cls, "_original_doc__", None)
    lines: list[str] = [f"# {cls.__name__}"]
    if original_doc:
        lines.append(original_doc.strip().split("\n")[0])
    lines.append("")
    lines.append("Values:")
    for member in cls:  # type: ignore[attr-defined]
        doc = _enum_member_doc(cls, member.name)
        entry = f"  {member.name} = {member.value!r}"
        if doc:
            entry += f"  -- {doc}"
        lines.append(entry)
    return "\n".join(lines)


def _enum_member_doc(cls: type, name: str) -> str:
    """Extract the inline docstring for an enum member, if any.

    Python 3.13+ stores the immediately-following ``\"\"\"docstring\"\"\"``
    literal as ``member.__doc__``. On older Pythons this is just the
    class docstring; we treat that as "no per-member doc" and return "".
    """
    member = cls[name]  # type: ignore[index]
    member_doc = getattr(member, "__doc__", None)
    if member_doc and member_doc != cls.__doc__:
        return _first_doc_line(member_doc)
    return ""


def _build_help(cls: type) -> str:
    """Build the help string for a class (not an instance).

    Works at decoration time with no instance available, so it inspects
    the class itself -- methods via the class dict, and type hints via
    ``__annotations__`` and ``__init__`` annotations.

    Args:
        cls: The class to document.

    Returns:
        A formatted multi-line help string.
    """
    lines: list[str] = [f"# {cls.__name__}"]

    # Preserve original docstring as the description line
    original_doc: str | None = getattr(cls, "_original_doc__", None)
    if original_doc:
        lines.append(original_doc.strip().split("\n")[0])

    lines.append("")

    # Collect type hints from __init__ and class-level annotations
    hints: dict[str, Any] = {}
    init = getattr(cls, "__init__", None)
    if init:
        hints.update(
            {
                k: v
                for k, v in getattr(init, "__annotations__", {}).items()
                if k != "return"
            }
        )
    hints.update(
        {k: v for k, v in getattr(cls, "__annotations__", {}).items()}
    )

    attrs: list[str] = []
    methods: list[str] = []

    seen: set[str] = set()
    for klass in cls.__mro__:
        for name, val in vars(klass).items():
            if name.startswith("_") or name in seen:
                continue
            seen.add(name)

            # Unwrap classmethod/staticmethod so they appear under Methods.
            call_target = _unwrap_callable(val)

            if callable(call_target) and not isinstance(val, property):
                try:
                    sig = _format_signature(call_target)
                except (ValueError, TypeError):
                    sig = "(...)"
                doc = _first_doc_line(getattr(call_target, "__doc__", None))
                entry = f"  {name}{sig}"
                if doc:
                    entry += f"  -- {doc}"
                methods.append(entry)
            else:
                if name in hints:
                    h = hints[name]
                    type_name: str = (
                        h.__name__ if isinstance(h, type) else str(h)
                    )
                else:
                    type_name = _type_label(val)
                attrs.append(f"  {name}: {type_name}")

    # Also show __init__ params as attributes if they're in hints but not
    # already declared on the class body
    for name, hint in hints.items():
        if name not in seen and not name.startswith("_"):
            type_name = hint.__name__ if isinstance(hint, type) else str(hint)
            attrs.append(f"  {name}: {type_name}")

    if attrs:
        lines.append("Attributes:")
        lines.extend(sorted(attrs))
        lines.append("")

    if methods:
        lines.append("Methods:")
        lines.extend(sorted(methods))

    return "\n".join(lines)


class _HelpableEnumMeta(EnumMeta):
    """Metaclass for enum classes that makes ``dir(EnumClass)`` clean.

    ``EnumType`` is the default metaclass for all ``Enum`` subclasses.
    By subclassing it and overriding ``__dir__``, ``dir(MyEnum)`` returns
    only the enum member names with values.
    """

    def __dir__(cls) -> list[str]:  # type: ignore[override]
        return better_dir(cls)


class _HelpableMeta(type):
    """Metaclass that makes ``dir(ClassName)`` return ``better_dir`` output.

    Without this, ``dir(cls)`` always calls ``type.__dir__(cls)`` which
    returns the raw attribute list including dunders.  By overriding
    ``__dir__`` on the metaclass, ``dir(MyClass)`` now returns the same
    clean list that ``dir(instance)`` does.
    """

    def __dir__(cls) -> list[str]:  # type: ignore[override]
        return better_dir(cls)


def helpable(cls: type) -> type:
    """Class decorator that wires ``better_dir`` and ``better_help`` automatically.

    Rewrites ``__doc__`` on the class at definition time so that ``help(obj)``
    shows a clean, AI-friendly summary through pydoc's normal machinery. Also
    installs ``__dir__`` to return ``better_dir(self)``.

    The original docstring is preserved in ``_original_doc__`` and used as the
    description line in the generated help output.

    Works on both classes and instances::

        @helpable
        class MyClient:
            \"\"\"A TCP client.\"\"\"
            ...

        dir(MyClient)      # clean output (via metaclass)
        dir(MyClient())    # clean output (via __dir__)
        help(MyClient)     # clean output (via __doc__)
        help(MyClient())   # clean output (via __doc__)

    Caveat:
        For classes whose metaclass is the default ``type``, the decorator
        recreates the class with ``_HelpableMeta`` so that ``dir(Class)``
        is also clean. Methods that use zero-argument ``super()`` inside
        such classes will still bind to the *original* class (via the
        ``__class__`` closure cell the compiler injects), which is not in
        the new class's MRO. In practice this is only an issue if the
        decorated class subclasses another class *and* its methods call
        ``super()``; keep ``@helpable`` for simple, leaf-level data/API
        classes, or use explicit ``super(ClassName, self)`` calls.

    Args:
        cls: The class to decorate.

    Returns:
        The decorated class with new ``__doc__`` and ``__dir__``.
    """
    original_doc = cls.__doc__

    # Stash original doc so _build_help can read it, then build help text.
    cls._original_doc__ = original_doc  # type: ignore[attr-defined]
    is_enum = isinstance(cls, type) and issubclass(cls, Enum)
    help_text = _build_enum_help(cls) if is_enum else _build_help(cls)

    def _dir(self: Any) -> list[str]:
        return better_dir(self)

    # If the metaclass is plain `type`, recreate the class with
    # _HelpableMeta so that dir(ClassName) also works.
    meta = type(cls)
    if meta is type:
        skip = {"__dict__", "__weakref__"}
        slots = vars(cls).get("__slots__", ())
        if slots:
            skip |= set(slots)
        ns = {k: v for k, v in vars(cls).items() if k not in skip}
        ns["__doc__"] = help_text
        ns["__dir__"] = _dir
        ns["_original_doc__"] = original_doc
        new_cls = _HelpableMeta(cls.__name__, cls.__bases__, ns)
        new_cls.__module__ = cls.__module__
        new_cls.__qualname__ = cls.__qualname__
        return new_cls  # type: ignore[return-value]

    # Fallback for classes with special metaclasses (Protocol, ABCMeta, …):
    # mutate in place — dir(instance) works, dir(Class) stays default.
    cls.__doc__ = help_text
    cls.__dir__ = _dir  # type: ignore[method-assign, assignment]
    return cls
