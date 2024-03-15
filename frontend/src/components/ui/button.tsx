/* Copyright 2024 Marimo. All rights reserved. */
import * as React from "react";
import { Slot } from "@radix-ui/react-slot";
import { VariantProps, cva } from "class-variance-authority";

import { cn } from "@/utils/cn";

const activeCommon = "active:shadow-xsSolid";

const buttonVariants = cva(
  cn(
    "disabled:opacity-50 disabled:pointer-events-none",
    "inline-flex mb-1 items-center justify-center rounded-md text-sm font-medium focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring focus-visible:ring-offset-2 ring-offset-background",
  ),
  {
    variants: {
      variant: {
        default: cn(
          "bg-primary text-primary-foreground hover:bg-primary/90 shadow-smSolid border border-primary",
          activeCommon,
        ),
        destructive: cn(
          "border shadow-smSolid",
          "bg-[var(--red-9)] hover:bg-[var(--red-10)] dark:bg-[var(--red-6)] dark:hover:bg-[var(--red-7)]",
          "text-[var(--red-1)] dark:text-[var(--red-12)]",
          "border-[var(--red-11)]",
          activeCommon,
        ),
        success: cn(
          "border shadow-smSolid",
          "bg-[var(--grass-9)] hover:bg-[var(--grass-10)] dark:bg-[var(--grass-6)] dark:hover:bg-[var(--grass-7)]",
          "text-[var(--grass-1)] dark:text-[var(--grass-12)]",
          "border-[var(--grass-11)]",
          activeCommon,
        ),
        warn: cn(
          "border shadow-smSolid",
          "bg-[var(--yellow-9)] hover:bg-[var(--yellow-10)] dark:bg-[var(--yellow-6)] dark:hover:bg-[var(--yellow-7)]",
          "text-[var(--yellow-12)]",
          "border-[var(--yellow-11)]",
          activeCommon,
        ),
        action: cn(
          "bg-action text-action-foreground shadow-smSolid",
          "hover:bg-action-hover border border-action",
          activeCommon,
        ),
        outline: cn(
          "border border-slate-300 shadow-smSolid",
          "hover:bg-accent hover:text-accent-foreground",
          "hover:border-primary",
          activeCommon,
        ),
        secondary: cn(
          "bg-secondary text-secondary-foreground hover:bg-secondary/80",
          "border border-input shadow-smSolid",
          activeCommon,
        ),
        text: cn("opacity-80 hover:opacity-100", "active:opacity-100"),
        ghost: cn(
          "hover:bg-accent hover:text-accent-foreground hover:shadow-smSolid border border-transparent",
          activeCommon,
          "active:text-accent-foreground",
        ),
        link: "underline-offset-4 hover:underline text-link",
      },
      size: {
        default: "h-10 py-2 px-4",
        xs: "h-7 px-2 rounded-md text-xs",
        sm: "h-9 px-3 rounded-md",
        lg: "h-11 px-8 rounded-md",
        icon: "h-6 w-6 mb-0",
      },
      disabled: {
        true: "opacity-50 pointer-events-none",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "sm",
    },
  },
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    Omit<VariantProps<typeof buttonVariants>, "disabled"> {
  asChild?: boolean;
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, ...props }, ref) => {
    const Comp = asChild ? Slot : "button";
    return (
      <Comp
        className={cn(
          buttonVariants({
            variant,
            size,
            className,
            disabled: props.disabled,
          }),
        )}
        ref={ref}
        {...props}
      />
    );
  },
);
Button.displayName = "Button";

export { Button, buttonVariants };
