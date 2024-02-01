/* Copyright 2024 Marimo. All rights reserved. */
import * as React from "react";

import { cn } from "@/utils/cn";
import { Events } from "@/utils/events";

export interface TextareaProps
  extends React.TextareaHTMLAttributes<HTMLTextAreaElement> {
  bottomAdornment?: React.ReactNode;
}

const Textarea = React.forwardRef<HTMLTextAreaElement, TextareaProps>(
  ({ className, bottomAdornment, ...props }, ref) => {
    return (
      <div className="relative">
        <textarea
          className={cn(
            "shadow-xsSolid hover:shadow-smSolid disabled:shadow-xsSolid focus-visible:shadow-mdSolid",
            "flex w-full mb-1 rounded-sm border border-input bg-background px-3 py-2 text-sm font-code ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring focus-visible:border-accent disabled:cursor-not-allowed disabled:opacity-50 min-h-[1.5rem]",
            className,
          )}
          onClick={Events.stopPropagation()}
          ref={ref}
          {...props}
        />
        {bottomAdornment && (
          <div className="absolute right-0 bottom-1 flex items-center pr-[6px] pointer-events-none text-muted-foreground h-6">
            {bottomAdornment}
          </div>
        )}
      </div>
    );
  },
);
Textarea.displayName = "Textarea";

export { Textarea };
