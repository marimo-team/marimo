# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import textwrap


def format_signature(prefix: str, signature_text: str, width: int = 39) -> str:
    black_installed = False
    try:
        import black

        black_installed = True
    except ModuleNotFoundError:
        pass

    if black_installed and (prefix.startswith(("class", "def"))):
        # Coarse try-except because we're using internal black APIs;
        # many other well-established projects use these APIs, which
        # gives us at least a small amount of confidence in our use.
        try:
            mode = black.Mode(line_length=width)  # type: ignore[attr-defined]
            # use "def " instead of class, since Jedi's class "signature" is
            # not actually valid syntax --- it's the init signature ...
            formatted = black.format_str(
                "def " + signature_text + ": ...", mode=mode
            )
            # replace "def " with actual prefix
            formatted = prefix + formatted[4:]
            # remove ": ..." body that was added to make valid syntax.
            # Black may keep ": ..." on the same line as the closing
            # paren (e.g. ") -> Html: ...") or put "..." on its own
            # indented line.
            formatted = formatted.rstrip()
            if formatted.endswith(": ..."):
                formatted = formatted[:-5]
            elif formatted.endswith("..."):
                formatted = formatted.rsplit("\n", 1)[0].rstrip()
                formatted = formatted.removesuffix(":")
            return formatted
        except Exception:
            pass

    return "\n  ".join(
        textwrap.wrap(
            # Make type-annotated arguments one word, so they
            # aren't broken by the wrapping
            prefix + signature_text.replace(": ", ":"),
            width=width,
            break_long_words=False,
        )
        # Re-expand type annotations
    ).replace(":", ": ")
