# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import locale

from marimo._utils.diagnostics import get_default_locale


def test_get_default_locale_uses_default_category(monkeypatch):
    """LC_ALL is not a valid getlocale category and must not be queried.

    On some platforms getlocale(LC_ALL) raises; on others it returns a
    mangled composite like "C/C". Either way the reported locale is wrong.
    """
    calls: list[int | None] = []

    def fake_getlocale(category=locale.LC_CTYPE):
        calls.append(category)
        if category == locale.LC_ALL:
            raise TypeError("category LC_ALL is not supported")
        return ("en_US", "UTF-8")

    monkeypatch.setattr(locale, "getlocale", fake_getlocale)

    assert get_default_locale() == "en_US"
    assert locale.LC_ALL not in calls


def test_get_default_locale_falls_back_to_env(monkeypatch):
    monkeypatch.setattr(locale, "getlocale", lambda *_: (None, None))
    monkeypatch.delattr(locale, "LC_MESSAGES", raising=False)
    for var in ("LC_ALL", "LC_MESSAGES", "LANG", "LANGUAGE"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("LANG", "fr_FR.UTF-8")

    assert get_default_locale() == "fr_FR"


def test_get_default_locale_returns_placeholder_when_unknown(monkeypatch):
    monkeypatch.setattr(locale, "getlocale", lambda *_: (None, None))
    monkeypatch.delattr(locale, "LC_MESSAGES", raising=False)
    for var in ("LC_ALL", "LC_MESSAGES", "LANG", "LANGUAGE"):
        monkeypatch.delenv(var, raising=False)

    assert get_default_locale() == "--"
