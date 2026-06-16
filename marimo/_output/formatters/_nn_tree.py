# Copyright 2026 Marimo. All rights reserved.
"""Shared presentation layer for neural-network module tree formatters.

Both the PyTorch (`pytorch_formatters`) and Flax NNX (`flax_formatters`)
formatters render a model as the same collapsible HTML tree. The data
extraction differs per framework, but the CSS, layout helpers, and footer
legend are identical and live here so they are defined once.
"""

from __future__ import annotations

import re
import typing

ModuleCategory = typing.Literal["weight", "act", "norm", "reg"]

_LABELS: dict[ModuleCategory, str] = {
    "weight": "Weight",
    "act": "Activation",
    "norm": "Normalization",
    "reg": "Regularization",
}

# Matches a comma followed by a space that is NOT inside parentheses.
_TOP_COMMA_RE = re.compile(r",\s+(?![^()]*\))")


def _comma_to_br(html_str: str) -> str:
    """Replace top-level comma separators with <br> for multi-line display.

    Also replaces the `=` between key/value pairs with a space for the
    expanded view, without touching `=` inside HTML attributes.
    """
    result = _TOP_COMMA_RE.sub("<br>", html_str)
    return result.replace("</span>=", "</span> ")


def _frozen_attr(is_frozen: bool) -> str:
    """Build the HTML data-frozen attribute string when needed."""
    if is_frozen:
        return ' data-frozen="true"'
    return ""


def _fmt_integer(n: int) -> str:
    """Format int into a human readable string."""
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return str(n)


def _footer_html() -> str:
    """Build the footer with the info-hover module-type legend."""
    legend_title = '<span class="nn-t-legend-title">Module types</span>'
    legend_items = "".join(
        f'<span class="nn-t-legend-item">'
        f'<span class="nn-t-swatch" data-cat="{cat}">'
        f'<span class="nn-t-swatch-dot"></span></span>{label}'
        f"</span>"
        for cat, label in _LABELS.items()
    )
    # Lucide "info" icon (ISC license)
    info_svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"'
        ' fill="none" stroke="currentColor" stroke-width="2"'
        ' stroke-linecap="round" stroke-linejoin="round">'
        '<circle cx="12" cy="12" r="10"/>'
        '<path d="M12 16v-4"/>'
        '<path d="M12 8h.01"/>'
        "</svg>"
    )
    return (
        f'<div class="nn-t-footer">'
        f'<span class="nn-t-info">{info_svg}'
        f'<span class="nn-t-legend">{legend_title}{legend_items}'
        f'<span class="nn-t-legend-sep"></span>'
        f'<span class="nn-t-legend-item">'
        f'<span class="nn-t-swatch"><span class="nn-t-swatch-dot"></span></span>'
        f"Trainable</span>"
        f'<span class="nn-t-legend-item">'
        f'<span class="nn-t-swatch" data-dim><span class="nn-t-swatch-dot"></span></span>'
        f"Frozen / no params</span>"
        f"</span>"
        f"</span>"
        f"</div>"
    )


_CSS = """\
.nn-t {
  font-size: 0.8125rem;
  line-height: 1.5;
  background-color: var(--slate-1);
  color: var(--slate-12);
  border-radius: 6px;
}

/* Header */
.nn-t-header {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.625rem 0.75rem 0.5rem 0.75rem;
}
.nn-t-root {
  font-family: monospace;
  font-size: 0.875rem;
  font-weight: 600;
  color: var(--slate-12);
}
.nn-t-summary {
  font-family: monospace;
  font-size: 0.75rem;
  color: var(--slate-11);
  margin-left: auto;
}
.nn-t-divider {
  height: 1px;
  background-color: var(--slate-3);
  margin: 0 0.75rem;
}

/* Body */
.nn-t-body {
  padding: 0.5rem 0 0.5rem 0.75rem;
}

/* Shared row layout */
.nn-t-leaf,
.nn-t-node > summary,
.nn-t-expand > summary {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.1875rem 0.75rem 0.1875rem 0;
  white-space: nowrap;
}
.nn-t-leaf:hover,
.nn-t-node > summary:hover,
.nn-t-expand > summary:hover {
  background: var(--slate-2);
}

/* Expandable nodes */
.nn-t-node {
  margin: 0;
  padding: 0;
}
.nn-t-node > summary {
  cursor: pointer;
  list-style: none;
}
.nn-t-node > summary::-webkit-details-marker {
  display: none;
}

/* Disclosure arrow */
.nn-t-arrow {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 1rem;
  flex-shrink: 0;
  color: var(--slate-9);
  transition: transform 0.12s;
  font-size: 0.5rem;
}
.nn-t-node[open] > summary .nn-t-arrow {
  transform: rotate(90deg);
}

/* Leaf spacer matches arrow width */
.nn-t-spacer {
  display: inline-block;
  width: 1rem;
  flex-shrink: 0;
}

/* Children with indent guide */
.nn-t-children {
  margin-left: calc(0.5rem - 1px);
  padding-left: 0.75rem;
  border-left: 1px solid var(--slate-3);
}

/* Text elements */
.nn-t-name {
  font-family: monospace;
  font-size: 0.8125rem;
  font-weight: 500;
  color: var(--slate-12);
}
.nn-t-type {
  font-family: monospace;
  font-size: 0.8125rem;
  font-weight: 600;
  color: var(--slate-12);
  padding: 0.0625rem 0.375rem;
  border-radius: 0.1875rem;
  background: var(--slate-3);
}
.nn-t-type[data-cat="weight"] { --pill-bg: var(--blue-3); --pill-fg: var(--blue-11); }
.nn-t-type[data-cat="norm"]   { --pill-bg: var(--green-3); --pill-fg: var(--green-11); }
.nn-t-type[data-cat="act"]    { --pill-bg: var(--orange-3); --pill-fg: var(--orange-11); }
.nn-t-type[data-cat="reg"]    { --pill-bg: var(--crimson-3); --pill-fg: var(--crimson-11); }
.nn-t-type[data-cat] {
  background: var(--pill-bg);
  color: var(--pill-fg);
}
/* Positional args (always visible, never truncated) */
.nn-t-pos {
  font-family: monospace;
  font-size: 0.8125rem;
  color: var(--slate-11);
  flex-shrink: 0;
}

/* Keyword args (truncated with ellipsis) */
.nn-t-args {
  font-family: monospace;
  font-size: 0.8125rem;
  color: var(--slate-11);
  overflow: hidden;
  text-overflow: ellipsis;
  min-width: 0;
}

/* Expandable args */
.nn-t-expand {
  margin: 0;
  padding: 0;
}
.nn-t-expand > summary {
  cursor: pointer;
  list-style: none;
}
.nn-t-expand > summary::-webkit-details-marker {
  display: none;
}
.nn-t-expand[open] > summary .nn-t-args {
  display: none;
}
.nn-t-expand-body {
  font-family: monospace;
  font-size: 0.8125rem;
  color: var(--slate-11);
  padding: 0 0.75rem 0.25rem 2.75rem;
  line-height: 1.6;
}
.nn-t-key {
  color: var(--slate-9);
}
.nn-t-expand-sep {
  display: flex;
  align-items: center;
  gap: 0.25rem;
  margin: 0.125rem 0 0 0;
}
.nn-t-expand-sep::after {
  content: "";
  flex: 1;
  height: 1px;
  background: var(--slate-3);
}
.nn-t-expand-sep-label {
  font-size: 0.5625rem;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--slate-8);
  flex-shrink: 0;
}

/* Param count */
.nn-t-params {
  color: var(--slate-10);
  font-family: monospace;
  font-size: 0.75rem;
  margin-left: auto;
  padding-left: 1rem;
  flex-shrink: 0;
}
[data-frozen] > .nn-t-type,
[data-frozen] > .nn-t-pos,
[data-frozen] > .nn-t-args,
[data-frozen] > .nn-t-params,
[data-frozen] > .nn-t-spacer,
[data-frozen] > summary > .nn-t-type,
[data-frozen] > summary > .nn-t-pos,
[data-frozen] > summary > .nn-t-args,
[data-frozen] > summary > .nn-t-params,
[data-frozen] > summary > .nn-t-arrow {
  opacity: 0.55;
}

/* Footer with info-hover legend */
.nn-t-footer {
  display: flex;
  justify-content: flex-end;
  padding: 0.25rem 0.75rem 0.375rem 0.75rem;
}
.nn-t-info {
  position: relative;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  color: var(--slate-8);
  cursor: default;
}
.nn-t-info:hover { color: var(--slate-10); }
.nn-t-info:hover .nn-t-legend {
  visibility: visible;
  opacity: 1;
}
.nn-t-info svg {
  width: 0.875rem;
  height: 0.875rem;
}
.nn-t-legend {
  visibility: hidden;
  opacity: 0;
  position: absolute;
  bottom: calc(100% + 6px);
  right: 0;
  z-index: 10;
  max-height: 12rem;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  padding: 0.375rem 0.625rem;
  background: var(--slate-1);
  border: 1px solid var(--slate-3);
  border-radius: 6px;
  white-space: nowrap;
  transition: opacity 0.12s, visibility 0.12s;
  font-family: monospace;
  font-size: 0.75rem;
  color: var(--slate-11);
}
.nn-t-legend-title {
  font-size: 0.6875rem;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--slate-9);
  margin-bottom: 0.0625rem;
}
.nn-t-legend-item {
  display: flex;
  align-items: center;
  gap: 0.375rem;
}
.nn-t-swatch {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 0.875rem;
  height: 0.8125rem;
  border-radius: 0.1875rem;
  flex-shrink: 0;
  background: var(--slate-3);
}
.nn-t-swatch[data-cat="weight"] { background: var(--blue-3); }
.nn-t-swatch[data-cat="norm"]   { background: var(--green-3); }
.nn-t-swatch[data-cat="act"]    { background: var(--orange-3); }
.nn-t-swatch[data-cat="reg"]    { background: var(--crimson-3); }
.nn-t-swatch-dot {
  width: 0.25rem;
  height: 0.25rem;
  border-radius: 50%;
  background: var(--slate-8);
}
.nn-t-swatch[data-cat="weight"] .nn-t-swatch-dot { background: var(--blue-11); }
.nn-t-swatch[data-cat="norm"] .nn-t-swatch-dot   { background: var(--green-11); }
.nn-t-swatch[data-cat="act"] .nn-t-swatch-dot    { background: var(--orange-11); }
.nn-t-swatch[data-cat="reg"] .nn-t-swatch-dot    { background: var(--crimson-11); }
.nn-t-swatch[data-dim] { opacity: 0.55; }
.nn-t-legend-sep {
  height: 1px;
  background: var(--slate-3);
  margin: 0.125rem 0;
}"""
