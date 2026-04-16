/* Copyright 2026 Marimo. All rights reserved. */

import type { CellValueSentinel, CellValueSentinelType } from "./types";

const WHITESPACE_MARKERS: Record<string, string> = {
  " ": "\u2423", // open box (space symbol)
  "\t": "\u2192", // right arrow
  "\n": "\u21B5", // return symbol
  "\r": "\u21B5", // return symbol (treat same as \n)
};

function renderWhitespaceMarkers(str: string): string {
  return [...str].map((ch) => WHITESPACE_MARKERS[ch] ?? ch).join("");
}

function describeWhitespace(str: string): string {
  const CHAR_NAMES: Record<string, string> = {
    " ": "space",
    "\t": "tab",
    "\n": "newline",
    "\r": "newline",
  };
  const counts: Record<string, number> = {};
  for (const ch of str) {
    const name = CHAR_NAMES[ch] ?? "character";
    counts[name] = (counts[name] ?? 0) + 1;
  }
  return Object.entries(counts)
    .map(([name, count]) => `${count} ${name}${count > 1 ? "s" : ""}`)
    .join(", ");
}

interface SentinelConfig {
  label: (value: CellValueSentinel["value"]) => string;
  tooltip: (value: CellValueSentinel["value"]) => string;
  ariaLabel: (value: CellValueSentinel["value"]) => string;
}

const SENTINEL_CONFIG: Record<CellValueSentinelType, SentinelConfig> = {
  null: {
    label: () => "None",
    tooltip: () => "None",
    ariaLabel: () => "None",
  },
  "empty-string": {
    label: () => "<empty>",
    tooltip: () => "<empty>",
    ariaLabel: () => "empty string",
  },
  whitespace: {
    label: (value) => renderWhitespaceMarkers(value as string),
    tooltip: (value) => describeWhitespace(value as string),
    ariaLabel: (value) => describeWhitespace(value as string),
  },
  nan: {
    label: () => "NaN",
    tooltip: () => "NaN",
    ariaLabel: () => "NaN",
  },
  "positive-infinity": {
    label: () => "inf",
    tooltip: () => "Infinity",
    ariaLabel: () => "infinity",
  },
  "negative-infinity": {
    label: () => "-inf",
    tooltip: () => "-Infinity",
    ariaLabel: () => "negative infinity",
  },
};

export function SentinelCell({
  sentinel,
}: {
  sentinel: CellValueSentinel;
}): React.ReactElement {
  const config = SENTINEL_CONFIG[sentinel.type];
  const label = config.label(sentinel.value);
  const tooltip = config.tooltip(sentinel.value);
  const ariaLabel = config.ariaLabel(sentinel.value);

  return (
    <span
      className="italic text-muted-foreground bg-muted rounded px-1"
      aria-label={ariaLabel}
      title={tooltip}
    >
      {label}
    </span>
  );
}
