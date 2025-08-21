/* Copyright 2024 Marimo. All rights reserved. */
import { cva } from "class-variance-authority";

export const calloutStyles = cva(
  "border rounded-lg p-12 mt-12 mb-12 text-foreground shadow-[4px_4px_0px_0px]",
  {
    variants: {
      kind: {
        neutral: "border-(--slate-9) shadow-(color:--slate-8)",
        // @deprecated, use danger instead
        alert: "bg-(--red-2) border-(--red-9) shadow-(color:--red-8)",
        info: "bg-(--sky-1) border-(--sky-8) shadow-(color:--sky-7)",
        danger: "bg-(--red-2) border-(--red-9) shadow-(color:--red-8)",
        warn: "bg-(--amber-2) border-(--amber-9) shadow-(color:--amber-8)",
        success: "bg-(--grass-2) border-(--grass-9) shadow-(color:--grass-8)",
      },
    },
    defaultVariants: {
      kind: "neutral",
    },
  },
);
