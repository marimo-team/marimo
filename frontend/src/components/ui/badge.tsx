/* Copyright 2026 Marimo. All rights reserved. */

import { cva, type VariantProps } from "class-variance-authority";
import * as React from "react";

import { cn } from "@/utils/cn";

const badgeVariants = cva(
  "inline-flex items-center border rounded-full px-2 py-0.5 text-xs font-semibold transition-colors focus:outline-hidden focus:ring-2 focus:ring-ring focus:ring-offset-2",
  {
    variants: {
      variant: {
        default:
          "bg-primary hover:bg-primary/60 border-transparent text-primary-foreground",
        defaultOutline: "bg-(--blue-2) border-(--blue-8) text-(--blue-11)",
        secondary:
          "bg-secondary hover:bg-secondary/80 border-transparent text-secondary-foreground",
        destructive:
          "bg-(--red-2) border-(--red-6) text-(--red-9) hover:bg-(--red-3)",
        success:
          "bg-(--grass-2) border-(--grass-5) text-(--grass-9) hover:bg-(--grass-3)",
        outline: "text-foreground",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  },
);

export interface BadgeProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof badgeVariants> {}

const Badge = ({ className, variant, ...props }: BadgeProps) => {
  return (
    <div className={cn(badgeVariants({ variant }), className)} {...props} />
  );
};

export { Badge, badgeVariants };
