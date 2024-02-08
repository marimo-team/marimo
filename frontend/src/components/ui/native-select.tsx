/* Copyright 2024 Marimo. All rights reserved. */
import * as React from "react";

import { cn } from "@/utils/cn";
import { Events } from "@/utils/events";
import { cva } from "class-variance-authority";

export const selectStyles = cva(
  "flex h-6 w-fit mb-1 items-center justify-between rounded-sm bg-background px-2 text-sm font-prose ring-offset-background placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-ring disabled:cursor-not-allowed disabled:opacity-50 cursor-pointer",
  {
    variants: {
      variant: {
        default:
          "shadow-xsSolid border border-input hover:shadow-smSolid focus:border-primary focus:shadow-mdSolid disabled:hover:shadow-xsSolid",
        ghost: "opacity-70 hover:opacity-100 focus:opacity-100",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  },
);

const NativeSelect = React.forwardRef<
  HTMLSelectElement,
  React.InputHTMLAttributes<HTMLSelectElement>
>(({ className, children, ...props }, ref) => (
  <select
    ref={ref}
    onClick={Events.stopPropagation()}
    className={cn(selectStyles({}), className)}
    {...props}
  >
    {children}
  </select>
));
NativeSelect.displayName = "NativeSelect";

export { NativeSelect };
