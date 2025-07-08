/* Copyright 2024 Marimo. All rights reserved. */

import { useControllableState } from "@radix-ui/react-use-controllable-state";
import { SearchIcon, XIcon } from "lucide-react";
import * as React from "react";
import {
  NumberField,
  type NumberFieldProps,
} from "@/components/ui/number-field";
import { useDebounceControlledState } from "@/hooks/useDebounce";
import { cn } from "@/utils/cn";
import { Events } from "@/utils/events";

export type InputProps = React.InputHTMLAttributes<HTMLInputElement> & {
  rootClassName?: string;
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
      <div className={cn("relative", props.rootClassName)}>
        {icon && (
          <div className="absolute inset-y-0 left-0 flex items-center pl-[6px] pointer-events-none text-muted-foreground">
            {icon}
          </div>
        )}
        <input
          type={type}
          className={cn(
            "shadow-xsSolid hover:shadow-smSolid disabled:shadow-xsSolid focus-visible:shadow-mdSolid",
            "flex h-6 w-full mb-1 rounded-sm border border-input bg-background px-1.5 py-1 text-sm font-code ring-offset-background file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring focus-visible:border-primary disabled:cursor-not-allowed disabled:opacity-50",
            icon && "pl-7",
            endAdornment && "pr-10",
            className,
          )}
          ref={ref}
          onClick={Events.stopPropagation()}
          {...props}
        />
        {endAdornment && (
          <div className="absolute inset-y-0 right-0 flex items-center pr-[6px] text-muted-foreground h-6">
            {endAdornment}
          </div>
        )}
      </div>
    );
  },
);
Input.displayName = "Input";

export const DebouncedInput = React.forwardRef<
  HTMLInputElement,
  InputProps & {
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
    <Input
      ref={ref}
      className={className}
      {...props}
      onChange={(evt) => onChange(evt.target.value)}
      value={value}
    />
  );
});
DebouncedInput.displayName = "DebouncedInput";

export const DebouncedNumberInput = React.forwardRef<
  HTMLInputElement,
  NumberFieldProps & {
    value: number;
    onValueChange: (valueAsNumber: number) => void;
  }
>(({ className, onValueChange, ...props }, ref) => {
  // Create a debounced value of 200
  const { value, onChange } = useDebounceControlledState<number>({
    initialValue: props.value,
    delay: 200,
    onChange: onValueChange,
  });

  return (
    <NumberField
      ref={ref}
      className={className}
      {...props}
      onChange={onChange}
      value={value}
    />
  );
});
DebouncedNumberInput.displayName = "DebouncedNumberInput";

export const SearchInput = React.forwardRef<
  HTMLInputElement,
  InputProps & {
    rootClassName?: string;
    icon?: React.ReactNode | null;
    clearable?: boolean;
  }
>(
  (
    {
      className,
      rootClassName,
      icon = <SearchIcon className="mr-2 h-4 w-4 shrink-0 opacity-50" />,
      clearable = true,
      ...props
    },
    ref,
  ) => {
    const uniqueId = React.useId();
    const inputId = props.id || uniqueId;
    return (
      <div className={cn("flex items-center border-b px-3", rootClassName)}>
        {icon}
        <input
          id={inputId}
          ref={ref}
          className={cn(
            "placeholder:text-foreground-muted flex h-7 m-1 w-full rounded-md bg-transparent py-3 text-sm outline-none disabled:cursor-not-allowed disabled:opacity-50",
            className,
          )}
          {...props}
        />
        {clearable && props.value && (
          <span
            onPointerDown={(e) => {
              e.preventDefault();
              e.stopPropagation();
              const input = document.getElementById(inputId);
              if (input && input instanceof HTMLInputElement) {
                input.focus();
                input.value = "";
                props.onChange?.({
                  ...e,
                  target: input,
                  currentTarget: input,
                  type: "change",
                } as React.ChangeEvent<HTMLInputElement>);
              }
            }}
          >
            <XIcon className="h-4 w-4 opacity-50 hover:opacity-90 cursor-pointer" />
          </span>
        )}
      </div>
    );
  },
);
SearchInput.displayName = "SearchInput";

export const OnBlurredInput = React.forwardRef<
  HTMLInputElement,
  InputProps & {
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
    <Input
      ref={ref}
      className={className}
      {...props}
      value={internalValue}
      onChange={(event) => setInternalValue(event.target.value)}
      onBlur={() => setValue(internalValue || "")}
      onKeyDown={(event) => {
        if (event.key !== "Enter") {
          return;
        }
        setValue(internalValue || "");
      }}
    />
  );
});
OnBlurredInput.displayName = "OnBlurredInput";

export { Input };
