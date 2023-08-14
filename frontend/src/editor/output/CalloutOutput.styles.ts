/* Copyright 2023 Marimo. All rights reserved. */
import { cva } from "class-variance-authority";

export const calloutStyles = cva(
  "border rounded-lg p-12 mt-12 mb-12 text-foreground shadow-[4px_4px_0px_0px]",
  {
    variants: {
      kind: {
        neutral: `bg-calloutNeutralBg border-calloutNeutralBorder shadow-calloutNeutralBorder`,
        alert: `bg-calloutAlertBg border-calloutAlertBorder shadow-calloutAlertBorder`,
        warn: `bg-calloutWarnBg border-calloutWarnBorder shadow-calloutWarnBorder`,
        success: `bg-calloutSuccessBg border-calloutSuccessBorder shadow-calloutSuccessBorder`,
      },
    },
    defaultVariants: {
      kind: "neutral",
    },
  }
);
