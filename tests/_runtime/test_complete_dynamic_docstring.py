from __future__ import annotations

import threading

from marimo._runtime.complete import (
    _get_completions_with_script,
    _get_runtime_completion_info,
)

SOURCE = '''
def interpolate_docstring(function):
    function.__doc__ = function.__doc__.format(
        parameter="expanded at runtime"
    )
    return function


@interpolate_docstring
def decorated(value):
    """Summary.\n\n{parameter}"""
    return value
'''


def _runtime_globals() -> dict[str, object]:
    glbls: dict[str, object] = {}
    exec(SOURCE, glbls)
    return glbls


def test_runtime_completion_info_resolves_static_placeholders() -> None:
    document = SOURCE + "\ndeco"
    _, static_completions = _get_completions_with_script([], document)

    completion_info = _get_runtime_completion_info(
        document,
        static_completions,
        _runtime_globals(),
        threading.RLock(),
    )

    assert {
        "names": list(completion_info),
        "has_runtime_text": "expanded at runtime"
        in completion_info["decorated"],
        "has_static_placeholder": "{parameter}"
        in completion_info["decorated"],
    } == {
        "names": ["decorated"],
        "has_runtime_text": True,
        "has_static_placeholder": False,
    }


def test_runtime_completion_info_preserves_literal_placeholders() -> None:
    source = '''
def documented(value):
    """Summary.\n\nExample: {name}"""
    return value
'''
    glbls: dict[str, object] = {}
    exec(source, glbls)
    document = source + "\ndocu"
    _, static_completions = _get_completions_with_script([], document)

    assert (
        _get_runtime_completion_info(
            document,
            static_completions,
            glbls,
            threading.RLock(),
        )
        == {}
    )
