/* Copyright 2023 Marimo. All rights reserved. */
import * as React from "react";
import { Slot } from "@radix-ui/react-slot";
import { VariantProps, cva } from "class-variance-authority";

import { cn } from "@/lib/utils";

const activeCommon = "active:shadow-xsSolid";

const buttonVariants = cva(
  "inline-flex mb-1 items-center justify-center rounded-md text-sm font-medium focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:opacity-50 disabled:pointer-events-none ring-offset-background",
  {
    variants: {
      variant: {
        default: cn(
          "bg-accent text-accent-foreground hover:bg-accent/90 shadow-smSolid border border-accent",
          activeCommon
        ),
        destructive: cn(
          "bg-destructive text-destructive-foreground shadow-smSolid",
          "hover:bg-destructive/90 border border-destructive",
          activeCommon
        ),
        action: cn(
          "bg-action text-action-foreground shadow-smSolid",
          "hover:bg-action-hover border border-action",
          activeCommon
        ),
        outline: cn(
          "border border-slate-500 shadow-smSolid",
          "hover:bg-accent/90 hover:text-accent-foreground",
          "hover:border-transparent",
          activeCommon
        ),
        secondary: cn(
          "bg-secondary text-secondary-foreground hover:bg-secondary/60",
          "border border-input shadow-smSolid",
          activeCommon
        ),
        ghost: cn(
          "hover:bg-accent/90 hover:text-accent-foreground hover:shadow-smSolid border border-transparent",
          activeCommon,
          "active:text-accent-foreground"
        ),
        link: "underline-offset-4 hover:underline text-primary",
      },
      size: {
        default: "h-10 py-2 px-4",
        sm: "h-9 px-3 rounded-md",
        xs: "h-7 px-2 rounded-md",
        lg: "h-11 px-8 rounded-md",
        icon: "h-6 w-6",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "sm",
    },
  }
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean;
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, ...props }, ref) => {
    const Comp = asChild ? Slot : "button";
    return (
      <Comp
        className={cn(buttonVariants({ variant, size, className }))}
        ref={ref}
        {...props}
      />
    );
  }
);
Button.displayName = "Button";

export { Button, buttonVariants };
