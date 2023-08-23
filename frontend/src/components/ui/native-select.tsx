/* Copyright 2023 Marimo. All rights reserved. */
import * as React from "react";

import { cn } from "@/lib/utils";

const NativeSelect = React.forwardRef<
  HTMLSelectElement,
  React.InputHTMLAttributes<HTMLSelectElement>
>(({ className, children, ...props }, ref) => (
  <select
    ref={ref}
    className={cn(
      "flex h-6 w-fit mb-1 shadow-xsSolid items-center justify-between rounded-sm border border-input bg-transparent px-2 text-sm font-prose ring-offset-background placeholder:text-muted-foreground hover:shadow-smSolid focus:outline-none focus:ring-1 focus:ring-ring focus:border-accent focus:shadow-mdSolid disabled:cursor-not-allowed disabled:opacity-50 cursor-pointer",
      className
    )}
    {...props}
  >
    {children}
  </select>
));
NativeSelect.displayName = "NativeSelect";

export { NativeSelect };
