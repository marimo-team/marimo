/* Copyright 2026 Marimo. All rights reserved. */
import React from "react";
import { cn } from "@/utils/cn";
import { Input } from "../ui/input";

export interface RegexInputProps {
  id?: string;
  value: string;
  onChange: (next: string) => void;
  onKeyDown?: (e: React.KeyboardEvent<HTMLInputElement>) => void;
  placeholder?: string;
  className?: string;
  autoFocus?: boolean;
  "aria-label"?: string;
}

export const RegexInput = React.forwardRef<HTMLInputElement, RegexInputProps>(
  (
    {
      id,
      value,
      onChange,
      onKeyDown,
      placeholder = "pattern",
      className,
      autoFocus,
      "aria-label": ariaLabel,
    },
    ref,
  ) => (
    <div
      className={cn(
        "flex items-stretch h-6 mb-1 rounded-sm border border-input bg-background shadow-xs-solid focus-within:shadow-md-solid focus-within:ring-1 focus-within:ring-ring focus-within:border-primary",
        className,
      )}
    >
      <Slash />
      <Input
        ref={ref}
        id={id}
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={onKeyDown}
        placeholder={placeholder}
        autoFocus={autoFocus}
        aria-label={ariaLabel}
        rootClassName="flex-1 min-w-0"
        className="border-0 mb-0 h-full shadow-none! hover:shadow-none! focus-visible:shadow-none! focus-visible:ring-0 focus-visible:border-0 rounded-none bg-transparent"
      />
      <Slash />
    </div>
  ),
);
RegexInput.displayName = "RegexInput";

const Slash = () => (
  <span className="px-1.5 flex items-center text-muted-foreground font-code text-sm select-none">
    /
  </span>
);
