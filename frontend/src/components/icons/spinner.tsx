/* Copyright 2024 Marimo. All rights reserved. */

import { cn } from "@/utils/cn";
import { VariantProps, cva } from "class-variance-authority";
import { Loader2Icon } from "lucide-react";
import React from "react";

const spinnerVariants = cva("animate-spin", {
  variants: {
    centered: {
      true: "m-auto",
    },
    size: {
      small: "size-4",
      medium: "size-12",
      large: "size-20",
      xlarge: "size-20",
    },
  },
  defaultVariants: {
    size: "medium",
  },
});

const Spinner = React.forwardRef<
  SVGSVGElement,
  React.SVGProps<SVGSVGElement> & VariantProps<typeof spinnerVariants>
>(({ className, children, centered, size, ...props }, ref) => (
  <Loader2Icon
    ref={ref}
    className={cn(spinnerVariants({ centered, size }), className)}
    strokeWidth={1.5}
    {...props}
  />
));
Spinner.displayName = "Spinner";

export { Spinner };
