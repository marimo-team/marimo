# Copyright 2026 Marimo. All rights reserved.
"""Copied from `validators`: https://github.com/python-validators/validators

Don't want to include the entire package as a dependency.
"""

from __future__ import annotations

import re

ip_middle_octet = r"(?:\.(?:1?\d{1,2}|2[0-4]\d|25[0-5]))"
ip_last_octet = r"(?:\.(?:0|[1-9]\d?|1\d\d|2[0-4]\d|25[0-5]))"

regex = re.compile(
    r"^"
    # protocol identifier
    r"(?:(?:https?|ftp)://)"
    # user:pass authentication
    r"(?:[-a-z\u00a1-\uffff0-9._~%!$&'()*+,;=:]+",
    # truncated for length - wait, this won't work, I need full content
