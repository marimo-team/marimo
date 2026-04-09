/* Copyright 2026 Marimo. All rights reserved. */
import { ChevronDown, ChevronUp } from "lucide-react";
import React from "react";
import {
  NumberField as AriaNumberField,
  type NumberFieldProps as AriaNumberFieldProps,
  Button,
  type ButtonProps,
  Input as RACInput,
  useLocale,
} from "react-aria-components";
import { cn } from "@/utils/cn";
import { maxFractionalDigits } from "@/utils/numbers";

export interface NumberFieldProps extends AriaNumberFieldProps {
  placeholder?: string;
  variant?: "default" | "xs";
  /**
   * Custom increment handler. When provided, the stepper buttons and
   * arrow keys call this instead of React Aria's built-in step behavior.
   * This avoids React Aria's step-snapping which forces values to align
   * with minValue + n*step.
   */
  onIncrement?: () => void;
  /** Custom decrement handler. See onIncrement. */
  onDecrement?: () => void;
}

export const NumberField = React.forwardRef<HTMLInputElement, NumberFieldProps>(
  (
    { placeholder, variant = "default", onIncrement, onDecrement, ...props },
    ref,
  ) => {
    const { locale } = useLocale();
    return (
      <AriaNumberField
        {...props}
        formatOptions={{
          minimumFractionDigits: 0,
          maximumFractionDigits: maxFractionalDigits(locale),
        }}
      >
        <div
          className={cn(
            "shadow-xs-solid hover:shadow-sm-solid hover:focus-within:shadow-md-solid",
            "flex overflow-hidden rounded-sm border border-input bg-background text-sm font-code ring-offset-background",
            "disabled:cursor-not-allowed disabled:opacity-50 disabled:shadow-xs-solid",
            "focus-within:shadow-md-solid focus-within:outline-hidden focus-within:ring-1 focus-within:ring-ring focus-within:border-primary",
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
                if (onIncrement || onDecrement) {
                  e.preventDefault();
                  if (e.key === "ArrowUp") {
                    onIncrement?.();
                  } else {
                    onDecrement?.();
                  }
                }
              }
            }}
            className={cn(
              "flex-1",
              "w-full",
              "placeholder:text-muted-foreground",
              "outline-hidden",
              "disabled:cursor-not-allowed disabled:opacity-50",
              variant === "default" ? "px-1.5" : "px-1",
            )}
          />
          <div className={"flex flex-col border-s-2"}>
            {onIncrement ? (
              <PlainStepperButton
                onClick={onIncrement}
                disabled={props.isDisabled}
                variant={variant}
                aria-label="Increment"
              >
                <ChevronUp
                  aria-hidden={true}
                  className={cn(
                    "w-3 h-3 -mb-px",
                    variant === "xs" && "w-2 h-2",
                  )}
                />
              </PlainStepperButton>
            ) : (
              <StepperButton
                slot="increment"
                isDisabled={props.isDisabled}
                variant={variant}
              >
                <ChevronUp
                  aria-hidden={true}
                  className={cn(
                    "w-3 h-3 -mb-px",
                    variant === "xs" && "w-2 h-2",
                  )}
                />
              </StepperButton>
            )}
            <div className={"h-px shrink-0 divider bg-border z-10"} />
            {onDecrement ? (
              <PlainStepperButton
                onClick={onDecrement}
                disabled={props.isDisabled}
                variant={variant}
                aria-label="Decrement"
              >
                <ChevronDown
                  aria-hidden={true}
                  className={cn(
                    "w-3 h-3 -mt-px",
                    variant === "xs" && "w-2 h-2",
                  )}
                />
              </PlainStepperButton>
            ) : (
              <StepperButton
                slot="decrement"
                isDisabled={props.isDisabled}
                variant={variant}
              >
                <ChevronDown
                  aria-hidden={true}
                  className={cn(
                    "w-3 h-3 -mt-px",
                    variant === "xs" && "w-2 h-2",
                  )}
                />
              </StepperButton>
            )}
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
        "cursor-default text-muted-foreground pressed:bg-muted-foreground group-disabled:text-disabled-foreground outline-hidden focus-visible:text-primary",
        "disabled:cursor-not-allowed disabled:opacity-50",
        !props.isDisabled && "hover:text-primary hover:bg-muted",
        props.variant === "default" ? "px-0.5" : "px-0.25",
      )}
    />
  );
};

const PlainStepperButton = (
  props: React.ButtonHTMLAttributes<HTMLButtonElement> & {
    variant?: "default" | "xs";
  },
) => {
  const { variant, ...rest } = props;
  return (
    <button
      type="button"
      tabIndex={-1}
      {...rest}
      className={cn(
        "cursor-default text-muted-foreground outline-hidden focus-visible:text-primary",
        "disabled:cursor-not-allowed disabled:opacity-50",
        !props.disabled && "hover:text-primary hover:bg-muted",
        variant === "default" || variant === undefined ? "px-0.5" : "px-0.25",
      )}
    />
  );
};
