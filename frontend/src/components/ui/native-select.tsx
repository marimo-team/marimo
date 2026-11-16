/* Copyright 2026 Marimo. All rights reserved. */

import { cva } from "class-variance-authority";
import * as React from "react";
import { cn } from "@/utils/cn";
import { Events } from "@/utils/events";

export const selectStyles = cva(
  "flex h-6 w-fit mb-1 items-center justify-between rounded-sm bg-background px-2 text-sm font-prose ring-offset-background placeholder:text-muted-foreground focus-visible:outline-hidden focus-visible:ring-1 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50 cursor-pointer forced-color-adjust-none forced-colors:bg-[ButtonFace] forced-colors:text-[ButtonText] forced-colors:disabled:text-[GrayText]",
  {
    variants: {
      variant: {
        default:
          "shadow-xs-solid border border-input hover:shadow-sm-solid focus-visible:border-primary focus-visible:shadow-md-solid disabled:hover:shadow-xs-solid forced-colors:border-[ButtonText] forced-colors:disabled:border-[GrayText]",
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
