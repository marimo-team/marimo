/* Copyright 2023 Marimo. All rights reserved. */
import * as React from "react";

import { cn } from "@/lib/utils";

export type TextareaProps = React.TextareaHTMLAttributes<HTMLTextAreaElement>;

const Textarea = React.forwardRef<HTMLTextAreaElement, TextareaProps>(
  ({ className, ...props }, ref) => {
    return (
      <textarea
        className={cn(
          "flex h-20 w-full mb-1 rounded-sm shadow-xsSolid border border-input bg-transparent px-3 py-2 text-sm font-code ring-offset-background placeholder:text-muted-foreground hover:shadow-smSolid focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring focus-visible:border-accent focus-visible:shadow-mdSolid disabled:cursor-not-allowed disabled:opacity-50",
          className
        )}
        ref={ref}
        {...props}
      />
    );
  }
);
Textarea.displayName = "Textarea";

export { Textarea };
