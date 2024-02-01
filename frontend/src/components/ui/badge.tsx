/* Copyright 2024 Marimo. All rights reserved. */
import * as React from "react";
import { VariantProps, cva } from "class-variance-authority";

import { cn } from "@/utils/cn";

const badgeVariants = cva(
  "inline-flex items-center border rounded-full px-2 py-0.5 text-xs font-semibold transition-colors focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2",
  {
    variants: {
      variant: {
        default:
          "bg-primary hover:bg-primary/80 border-transparent text-primary-foreground",
        secondary:
          "bg-secondary hover:bg-secondary/80 border-transparent text-secondary-foreground",
        destructive:
          "bg-[var(--red-2)] border-[var(--red-6)] text-[var(--red-9)] hover:bg-[var(--red-3)]",
        success:
          "bg-[var(--grass-2)] border-[var(--grass-5)] text-[var(--grass-9)] hover:bg-[var(--grass-3)]",
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
