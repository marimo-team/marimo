/* Copyright 2024 Marimo. All rights reserved. */
import { ChevronUp, ChevronDown } from "lucide-react";
import {
  NumberField as AriaNumberField,
  type NumberFieldProps as AriaNumberFieldProps,
  Button,
  type ButtonProps,
  Input as RACInput,
} from "react-aria-components";
import React from "react";
import { cn } from "@/utils/cn";

export interface NumberFieldProps extends AriaNumberFieldProps {
  placeholder?: string;
  variant?: "default" | "xs";
}

export const NumberField = React.forwardRef<HTMLInputElement, NumberFieldProps>(
  ({ placeholder, variant = "default", ...props }, ref) => {
    return (
      <AriaNumberField
        {...props}
        formatOptions={{
          minimumFractionDigits: 0,
          maximumFractionDigits: 100,
        }}
      >
        <div
          className={cn(
            "shadow-xsSolid hover:shadow-smSolid hover:focus-within:shadow-mdSolid",
            "flex overflow-hidden rounded-sm border border-input bg-background text-sm font-code ring-offset-background",
            "disabled:cursor-not-allowed disabled:opacity-50 disabled:shadow-xsSolid",
            "focus-within:shadow-mdSolid focus-within:outline-none focus-within:ring-1 focus-within:ring-ring focus-within:border-primary",
            variant === "default" ? "h-6 w-full mb-1" : "h-4 w-full mb-0.5",
            variant === "xs" && "text-xs",
            props.className,
          )}
        >
          <RACInput
            ref={ref}
            disabled={props.isDisabled}
            placeholder={placeholder}
            onKeyDown={(e) => {
              if (e.key === "ArrowUp" || e.key === "ArrowDown") {
                e.stopPropagation();
              }
            }}
            className={cn(
              "flex-1",
              "w-full",
              "placeholder:text-muted-foreground",
              "outline-none",
              "disabled:cursor-not-allowed disabled:opacity-50",
              variant === "default" ? "px-1.5" : "px-1",
            )}
          />
          <div className={"flex flex-col border-s-2"}>
            <StepperButton
              slot="increment"
              isDisabled={props.isDisabled}
              variant={variant}
            >
              <ChevronUp
                aria-hidden={true}
                className={cn(
                  "w-3 h-3 -mb-[1px]",
                  variant === "xs" && "w-2 h-2",
                )}
              />
            </StepperButton>
            <div className={"h-[1px] flex-shrink-0 divider bg-border z-10"} />
            <StepperButton
              slot="decrement"
              isDisabled={props.isDisabled}
              variant={variant}
            >
              <ChevronDown
                aria-hidden={true}
                className={cn(
                  "w-3 h-3 -mt-[1px]",
                  variant === "xs" && "w-2 h-2",
                )}
              />
            </StepperButton>
          </div>
        </div>
      </AriaNumberField>
    );
  },
);
NumberField.displayName = "NumberField";

const StepperButton = (props: ButtonProps & { variant?: "default" | "xs" }) => {
  return (
    <Button
      {...props}
      className={cn(
        "cursor-default text-muted-foreground pressed:bg-muted-foreground group-disabled:text-disabled-foreground outline-none focus-visible:text-primary",
        "disabled:cursor-not-allowed disabled:opacity-50",
        !props.isDisabled && "hover:text-primary hover:bg-muted",
        props.variant === "default" ? "px-0.5" : "px-0.25",
      )}
    />
  );
};
