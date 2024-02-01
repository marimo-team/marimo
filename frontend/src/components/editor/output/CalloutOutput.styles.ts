/* Copyright 2024 Marimo. All rights reserved. */
import { cva } from "class-variance-authority";

export const calloutStyles = cva(
  "border rounded-lg p-12 mt-12 mb-12 text-foreground shadow-[4px_4px_0px_0px]",
  {
    variants: {
      kind: {
        neutral: `border-[var(--slate-9)] shadow-[var(--slate-8)]`,
        // @deprecated, use danger instead
        alert: `bg-[var(--red-2)] border-[var(--red-9)] shadow-[var(--red-8)]`,
        info: `bg-[var(--sky-1)] border-[var(--sky-8)] shadow-[var(--sky-7)]`,
        danger: `bg-[var(--red-2)] border-[var(--red-9)] shadow-[var(--red-8)]`,
        warn: `bg-[var(--amber-2)] border-[var(--amber-9)] shadow-[var(--amber-8)]`,
        success: `bg-[var(--grass-2)] border-[var(--grass-9)] shadow-[var(--grass-8)]`,
      },
    },
    defaultVariants: {
      kind: "neutral",
    },
  },
);
