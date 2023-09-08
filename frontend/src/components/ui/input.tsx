/* Copyright 2023 Marimo. All rights reserved. */
import * as React from "react";

import { cn } from "@/lib/utils";

export type InputProps = React.InputHTMLAttributes<HTMLInputElement> & {
  icon?: React.ReactNode;
};

const Input = React.forwardRef<HTMLInputElement, InputProps>(
  ({ className, type, ...props }, ref) => {
    const icon = props.icon;

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
            "flex h-6 w-full mb-1 rounded-sm shadow-xsSolid border border-input bg-transparent px-1.5 py-1 text-sm font-code ring-offset-background file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-muted-foreground hover:shadow-smSolid focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring focus-visible:border-primary focus-visible:shadow-mdSolid disabled:cursor-not-allowed disabled:opacity-50",
            icon && "pl-7",
            className
          )}
          ref={ref}
          {...props}
        />
      </div>
    );
  }
);
Input.displayName = "Input";

export { Input };
