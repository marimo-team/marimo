/* Copyright 2024 Marimo. All rights reserved. */
import { ChevronUp, ChevronDown } from "lucide-react";
import {
  NumberField as AriaNumberField,
  NumberFieldProps as AriaNumberFieldProps,
  Button,
  ButtonProps,
  Input as RACInput,
} from "react-aria-components";
import React from "react";
import { cn } from "@/utils/cn";

export interface NumberFieldProps extends AriaNumberFieldProps {
  placeholder?: string;
}

export const NumberField = React.forwardRef<HTMLInputElement, NumberFieldProps>(
  ({ placeholder, ...props }, ref) => {
    return (
      <AriaNumberField {...props}>
        <div
          className={cn(
            "shadow-xsSolid hover:shadow-smSolid hover:focus-within:shadow-mdSolid",
            "flex h-6 w-full mb-1  overflow-hidden rounded-sm border border-input bg-background text-sm font-code ring-offset-background",
            "disabled:cursor-not-allowed disabled:opacity-50 disabled:shadow-xsSolid",
            "focus-within:shadow-mdSolid focus-within:outline-none focus-within:ring-1 focus-within:ring-ring focus-within:border-primary",
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
              "px-1.5",
            )}
          />
          <div className={"flex flex-col border-s-2"}>
            <StepperButton slot="increment" isDisabled={props.isDisabled}>
              <ChevronUp aria-hidden={true} className="w-3 h-3 -mb-[1px]" />
            </StepperButton>
            <div className={"h-[1px] flex-shrink-0 divider bg-border z-10"} />
            <StepperButton slot="decrement" isDisabled={props.isDisabled}>
              <ChevronDown aria-hidden={true} className="w-3 h-3 -mt-[1px]" />
            </StepperButton>
          </div>
        </div>
      </AriaNumberField>
    );
  },
);
NumberField.displayName = "NumberField";

const StepperButton = (props: ButtonProps) => {
  return (
    <Button
      {...props}
      className={cn(
        "px-0.5 cursor-default text-muted-foreground pressed:bg-muted-foreground group-disabled:text-disabled-foreground outline-none focus-visible:text-primary",
        "disabled:cursor-not-allowed disabled:opacity-50",
        !props.isDisabled && "hover:text-primary hover:bg-muted",
      )}
    />
  );
};
