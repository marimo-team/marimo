/* Copyright 2026 Marimo. All rights reserved. */

import type React from "react";

export const Chip = ({ children }: { children: React.ReactNode }) => (
  <span className="inline-flex items-center rounded-sm bg-muted/50 px-1 font-mono text-xs font-normal leading-tight text-foreground">
    {children}
  </span>
);

export const MoreChip = ({ count }: { count: number }) => (
  <span className="inline-flex items-center px-1 text-xs italic text-muted-foreground">
    +{count}
  </span>
);

interface ChipWithCommaProps {
  value: string;
  showComma: boolean;
}

export const ChipWithComma = ({ value, showComma }: ChipWithCommaProps) => (
  <span className="inline-flex items-center">
    <Chip>{value}</Chip>
    {showComma && <span className="text-muted-foreground">,</span>}
  </span>
);

interface CompactChipRowProps {
  items: string[];
  max?: number;
}

export const CompactChipRow = ({ items, max = 3 }: CompactChipRowProps) => {
  if (items.length === 0) {
    return null;
  }
  const visible = items.slice(0, max);
  const hidden = Math.max(0, items.length - max);
  return (
    <span className="inline-flex items-center gap-1">
      {visible.map((item, i) => (
        <ChipWithComma
          key={i}
          value={item}
          showComma={i < visible.length - 1}
        />
      ))}
      {hidden > 0 && <MoreChip count={hidden} />}
    </span>
  );
};
