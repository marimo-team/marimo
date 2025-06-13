/* Copyright 2024 Marimo. All rights reserved. */

import { useControllableState } from "@radix-ui/react-use-controllable-state";
import * as React from "react";
import { useDebounceControlledState } from "@/hooks/useDebounce";
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

export const DebouncedTextarea = React.forwardRef<
  HTMLTextAreaElement,
  TextareaProps & {
    value: string;
    onValueChange: (value: string) => void;
    delay?: number;
  }
>(({ className, onValueChange, ...props }, ref) => {
  const { value, onChange } = useDebounceControlledState<string>({
    initialValue: props.value,
    delay: props.delay,
    onChange: onValueChange,
  });

  return (
    <Textarea
      ref={ref}
      className={className}
      {...props}
      onChange={(evt) => onChange(evt.target.value)}
      value={value}
    />
  );
});
DebouncedTextarea.displayName = "DebouncedTextarea";

export const OnBlurredTextarea = React.forwardRef<
  HTMLTextAreaElement,
  TextareaProps & {
    value: string;
    onValueChange: (value: string) => void;
  }
>(({ className, onValueChange, ...props }, ref) => {
  const [internalValue, setInternalValue] = React.useState(props.value);

  const [value, setValue] = useControllableState<string>({
    prop: props.value,
    defaultProp: internalValue,
    onChange: onValueChange,
  });

  React.useEffect(() => {
    setInternalValue(value || "");
  }, [value]);

  return (
    <Textarea
      ref={ref}
      className={className}
      {...props}
      value={internalValue}
      onChange={(event) => setInternalValue(event.target.value)}
      onBlur={() => setValue(internalValue)}
      onKeyDown={(event) => {
        if (!(event.ctrlKey && event.key === "Enter")) {
          return;
        }
        event.preventDefault();
        setValue(internalValue);
      }}
    />
  );
});
OnBlurredTextarea.displayName = "OnBlurredTextarea";

export { Textarea };
