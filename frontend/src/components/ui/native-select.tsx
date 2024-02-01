/* Copyright 2024 Marimo. All rights reserved. */
import * as React from "react";

import { cn } from "@/utils/cn";
import { Events } from "@/utils/events";
import { cva } from "class-variance-authority";

export const selectStyles = cva(
  "flex h-6 w-fit mb-1 shadow-xsSolid items-center justify-between rounded-sm border border-input bg-background px-2 text-sm font-prose ring-offset-background placeholder:text-muted-foreground hover:shadow-smSolid focus:outline-none focus:ring-1 focus:ring-ring focus:border-primary focus:shadow-mdSolid disabled:cursor-not-allowed disabled:opacity-50 cursor-pointer",
  {
    variants: {},
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
