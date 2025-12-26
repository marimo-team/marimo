# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import re

from marimo._utils.platform import is_windows

cmd_meta = r"([\"\^\&\|\<\>\(\)\%\!])"
cmd_meta_or_space = r"[\s\"\^\&\|\<\>\(\)\%\!]"
cmd_meta_inside_quotes = r"([\"\%\!])"


def _wrap_in_quotes(s: str) -> str:
    """
    From mslex: https://github.com/smoofra/mslex/blob/master/mslex
    Under Apache License 2.0: https://www.apache.org/licenses/LICENSE-2.0

    Wrap a string whose internal quotes have been escaped in double quotes.
    This handles adding the correct number of backslashes in front of the
    closing quote.
    """
    return '"' + re.sub(r"(\\+)$", r"\1\1", s) + '"'


def _quote_for_cmd(s: str) -> str:
    """
    From mslex: https://github.com/smoofra/mslex/blob/master/mslex
    Under Apache License 2.0: https://www.apache.org/licenses/LICENSE-2.0

    Quote a string for cmd. Split the string into sections that can be
    quoted (or used verbatim), and runs of % and ! characters which must be
    escaped with carets outside of quotes, and runs of quote characters,
    which must be escaped with a caret for cmd.exe, and a backslash for
    CommandLineToArgvW.
    """

    def f(m: re.Match[str]) -> str:
        quotable, subst = m.groups()
        if quotable:
            # A trailing backslash could combine a backslash escaping a
            # quote, so it must be quoted
            if re.search(cmd_meta_or_space, quotable) or quotable.endswith(
                "\\"
            ):
                return _wrap_in_quotes(quotable)
            else:
                return quotable
        elif subst:
            return "^" + subst
        else:
            return '\\^"'

    return re.sub(r'([^\%\!\"]+)|([\%\!])|"', f, s)


def _mslex_quote(s: str) -> str:
    """
    From mslex: https://github.com/smoofra/mslex/blob/master/mslex
    Under Apache License 2.0: https://www.apache.org/licenses/LICENSE-2.0

    Quote a string for use as a command line argument in DOS or Windows.

    :param s: a string to quote
    :param for_cmd: quote it for ``cmd.exe``
    :return: quoted string

    If ``for_cmd`` is true, then this will quote the strings so the result will
    be parsed correctly by ``cmd.exe`` and then by ``CommandLineToArgvW``.   If
    false, then this will quote the strings so the result will
    be parsed correctly when passed directly to ``CommandLineToArgvW``.
    """
    if not s:
        return '""'

    if not re.search(cmd_meta_or_space, s):
        return s
    quoted = _quote_for_cmd(s)
    if not re.search(r"[\s\"]", s):
        # for example the string «x\!» can be quoted as «x\^!», but
        # _quote_for_cmd would quote it as «"x\\"^!»
        alt = re.sub(cmd_meta, r"^\1", s)
        if len(alt) < len(quoted):
            return alt
    return quoted


def cmd_quote(s: str) -> str:
    """
    Quote a string for use as a command line argument in Windows or POSIX.
    """
    if is_windows():
        return _mslex_quote(s)
    import shlex

    return shlex.quote(s)


def standardize_annotation_quotes(annotation: str) -> str:
    """Standardize quotes in type annotations to use double quotes.

    This handles complex cases like Literal['foo', 'bar'] -> Literal["foo", "bar"]
    while preserving mixed quote scenarios where double quotes are already present.

    Args:
        annotation: The type annotation string to standardize

    Returns:
        The annotation string with standardized double quotes

    Examples:
        >>> standardize_annotation_quotes("Literal['foo', 'bar']")
        'Literal["foo", "bar"]'
        >>> standardize_annotation_quotes("Literal['say \"hello\"']")
        'Literal[\'say "hello"\']'  # Preserved due to internal double quotes
        >>> standardize_annotation_quotes("int")
        'int'  # No quotes to standardize
    """

    # Regex pattern to match string literals within the annotation:
    #
    # '([^'\\]*(?:\\.[^'\\]*)*)'  - Matches single-quoted strings:
    #   - '                       - Opening single quote
    #   - ([^'\\]*                - Capture group: any chars except ' and \
    #   - (?:\\.[^'\\]*)*         - Non-capturing group: escaped char followed by non-quote/backslash chars, repeated
    #   - )'                      - Closing single quote and end capture group
    #
    # |                           - OR operator
    #
    # "([^"\\]*(?:\\.[^"\\]*)*)"  - Matches double-quoted strings:
    #   - "                       - Opening double quote
    #   - ([^"\\]*                - Capture group: any chars except " and \
    #   - (?:\\.[^"\\]*)*         - Non-capturing group: escaped char followed by non-quote/backslash chars, repeated
    #   - )"                      - Closing double quote and end capture group
    #
    # This pattern correctly handles escaped quotes within strings like 'it\'s' or "say \"hello\""
    string_pattern = (
        r"'([^'\\]*(?:\\.[^'\\]*)*)'|\"([^\"\\]*(?:\\.[^\"\\]*)*)\""
    )

    def replace_quotes(match: re.Match[str]) -> str:
        if match.group(1) is not None:  # Single quoted string matched
            content = match.group(1)
            # Check if the content contains unescaped double quotes
            # If so, keep as single quotes to avoid escaping issues
            if '"' in content and '\\"' not in content:
                return match.group(0)  # Keep original single-quoted string
            else:
                # Convert to double quotes, handling escaped characters properly
                content = content.replace("\\'", "'")  # Unescape single quotes
                content = content.replace(
                    '"', '\\"'
                )  # Escape any double quotes
                return f'"{content}"'
        else:  # Double quoted string matched (group 2)
            return match.group(0)  # Keep as is - already using double quotes

    return re.sub(string_pattern, replace_quotes, annotation)
