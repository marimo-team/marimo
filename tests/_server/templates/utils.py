from __future__ import annotations

import os
import re


def remove_hash_from_href(url: str) -> str:
    base, ext = os.path.splitext(url)
    if len(base) < 10:
        return url
    if base[-9] == "-":  # Hash is 9 characters long
        return f'{base[:-9]}{ext}"'
    return url


def normalize_index_html(index_html: str) -> str:
    # Remove the hash from the URLs in the index.html
    # And remove the version
    # This is so the snapshots can stay stable across versions
    index_html = re.sub(
        r'href="[^"]+"',
        lambda x: remove_hash_from_href(x.group(0)),
        index_html,
    )
    index_html = re.sub(
        r"href='[^']+'",
        lambda x: remove_hash_from_href(x.group(0)),
        index_html,
    )
    index_html = re.sub(
        r'src="[^"]+"',
        lambda x: remove_hash_from_href(x.group(0)),
        index_html,
    )
    index_html = re.sub(
        r"src='[^']+'",
        lambda x: remove_hash_from_href(x.group(0)),
        index_html,
    )
    return index_html
