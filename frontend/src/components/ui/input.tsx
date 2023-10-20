/* Copyright 2023 Marimo. All rights reserved. */
import * as React from "react";

import { cn } from "@/lib/utils";

export type InputProps = React.InputHTMLAttributes<HTMLInputElement> & {
  icon?: React.ReactNode;
  endAdornment?: React.ReactNode;
};

const Input = React.forwardRef<HTMLInputElement, InputProps>(
  ({ className, type, endAdornment, ...props }, ref) => {
    const icon = props.icon;

    if (type === "hidden") {
      return <input type="hidden" ref={ref} {...props} />;
    }

    return (
      <div className="relative">
        {icon && (
          <div className="absolute inset-y-0 left-0 flex items-center pl-[6px] pointer-events-none text-muted-foreground h-6">
            {icon}
          </div>
        )}
        <input
          type={type}
          className={cn(
            "shadow-xsSolid hover:shadow-smSolid disabled:shadow-xsSolid focus-visible:shadow-mdSolid",
            "flex h-6 w-full mb-1 rounded-sm border border-input bg-transparent px-1.5 py-1 text-sm font-code ring-offset-background file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring focus-visible:border-primary disabled:cursor-not-allowed disabled:opacity-50",
            icon && "pl-7",
            endAdornment && "pr-10",
            className
          )}
          ref={ref}
          {...props}
        />
        {endAdornment && (
          <div className="absolute inset-y-0 right-0 flex items-center pr-[6px] pointer-events-none text-muted-foreground h-6">
            {endAdornment}
          </div>
        )}
      </div>
    );
  }
);
Input.displayName = "Input";

export { Input };
