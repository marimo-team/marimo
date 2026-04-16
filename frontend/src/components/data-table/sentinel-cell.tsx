/* Copyright 2026 Marimo. All rights reserved. */

import type { CellValueSentinel, CellValueSentinelType } from "./types";

const WHITESPACE_CHARS: Record<string, { marker: string; name: string }> = {
  " ": { marker: "\u2423", name: "space" }, // open box (space symbol)
  "\t": { marker: "\\t", name: "tab" },
  "\n": { marker: "\\n", name: "newline" },
  "\r": { marker: "\\r", name: "newline" },
};

function renderWhitespaceMarkers(str: string): string {
  return [...str].map((ch) => WHITESPACE_CHARS[ch]?.marker ?? ch).join("");
}

function describeWhitespace(str: string): string {
  const counts: Record<string, number> = {};
  for (const ch of str) {
    const name = WHITESPACE_CHARS[ch]?.name ?? "character";
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
    label: (value) => renderWhitespaceMarkers(String(value)),
    tooltip: (value) => describeWhitespace(String(value)),
    ariaLabel: (value) => describeWhitespace(String(value)),
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
  nat: {
    label: () => "NaT",
    tooltip: () => "NaT (Not a Time)",
    ariaLabel: () => "Not a Time",
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
      <span className="opacity-70">{label}</span>
    </span>
  );
}
