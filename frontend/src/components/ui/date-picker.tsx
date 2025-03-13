/* Copyright 2024 Marimo. All rights reserved. */
import { CalendarIcon } from "lucide-react";
import {
  DatePicker as AriaDatePicker,
  type DatePickerProps as AriaDatePickerProps,
  DateRangePicker as AriaDateRangePicker,
  Dialog as AriaDialog,
  Button as AriaButton,
  type DateRangePickerProps as AriaDateRangePickerProps,
  type DateValue as AriaDateValue,
  type DialogProps as AriaDialogProps,
  type PopoverProps as AriaPopoverProps,
  type ValidationResult as AriaValidationResult,
  composeRenderProps,
  Text,
} from "react-aria-components";

import { buttonVariants } from "./button";
import {
  Calendar,
  CalendarCell,
  CalendarGrid,
  CalendarGridBody,
  CalendarGridHeader,
  CalendarHeaderCell,
  CalendarHeading,
  RangeCalendar,
} from "./calendar";
import { cn } from "@/utils/cn";
import { FieldGroup, FieldError, Label } from "./field";
import { DateInput } from "./date-input";
import { Popover } from "./aria-popover";
import { useState } from "react";

const DatePickerContent = ({
  className,
  popoverClassName,
  ...props
}: AriaDialogProps & { popoverClassName?: AriaPopoverProps["className"] }) => (
  <Popover
    className={composeRenderProps(popoverClassName, (className) =>
      cn("w-auto p-3", className),
    )}
  >
    <AriaDialog
      className={cn(
        "flex w-full flex-col space-y-4 outline-none sm:flex-row sm:space-x-4 sm:space-y-0",
        className,
      )}
      {...props}
    />
  </Popover>
);

interface DatePickerProps<T extends AriaDateValue>
  extends AriaDatePickerProps<T> {
  label?: string;
  description?: string;
  errorMessage?: string | ((validation: AriaValidationResult) => string);
}

const DatePicker = <T extends AriaDateValue>({
  label,
  description,
  errorMessage,
  className,
  ...props
}: DatePickerProps<T>) => {
  const [open, setOpen] = useState(false);
  return (
    <AriaDatePicker
      isOpen={open}
      className={composeRenderProps(className, (className) =>
        cn("group flex flex-col gap-2", className),
      )}
      onOpenChange={(open) => {
        setOpen(open);
      }}
      {...props}
    >
      {label && <Label>{label}</Label>}
      <FieldGroup>
        <DateInput aria-label="date input" className="flex-1" variant="ghost" />
        <AriaButton
          onPressChange={() => {
            setOpen(true);
          }}
          className={cn(
            buttonVariants({ variant: "text", size: "icon" }),
            "ml-1 size-6 data-[focus-visible]:ring-offset-0",
          )}
        >
          <CalendarIcon aria-hidden={true} className="size-4" />
        </AriaButton>
      </FieldGroup>
      {description && (
        <Text className="text-sm text-muted-foreground" slot="description">
          {description}
        </Text>
      )}
      <FieldError>{errorMessage}</FieldError>
      <DatePickerContent>
        <Calendar>
          <CalendarHeading />
          <CalendarGrid>
            <CalendarGridHeader>
              {(day) => <CalendarHeaderCell>{day}</CalendarHeaderCell>}
            </CalendarGridHeader>
            <CalendarGridBody>
              {(date) => <CalendarCell date={date} />}
            </CalendarGridBody>
          </CalendarGrid>
        </Calendar>
      </DatePickerContent>
    </AriaDatePicker>
  );
};

interface DateRangePickerProps<T extends AriaDateValue>
  extends AriaDateRangePickerProps<T> {
  label?: string;
  description?: string;
  errorMessage?: string | ((validation: AriaValidationResult) => string);
}

const DateRangePicker = <T extends AriaDateValue>({
  label,
  description,
  errorMessage,
  className,
  ...props
}: DateRangePickerProps<T>) => {
  const [open, setOpen] = useState(false);
  return (
    <AriaDateRangePicker
      isOpen={open}
      className={composeRenderProps(className, (className) =>
        cn("group flex flex-col gap-2", className),
      )}
      onOpenChange={(open) => {
        setOpen(open);
      }}
      {...props}
    >
      <Label>{label}</Label>
      <FieldGroup>
        <DateInput variant="ghost" slot={"start"} />
        <span aria-hidden={true} className="px-2 text-sm text-muted-foreground">
          -
        </span>
        <DateInput className="flex-1" variant="ghost" slot={"end"} />

        <AriaButton
          onPressChange={() => {
            setOpen(true);
          }}
          className={cn(
            buttonVariants({ variant: "text", size: "icon" }),
            "ml-1 size-6 data-[focus-visible]:ring-offset-0",
          )}
        >
          <CalendarIcon aria-hidden={true} className="size-4" />
        </AriaButton>
      </FieldGroup>
      {description && (
        <Text className="text-sm text-muted-foreground" slot="description">
          {description}
        </Text>
      )}
      <FieldError>{errorMessage}</FieldError>
      <DatePickerContent>
        <RangeCalendar>
          <CalendarHeading />
          <CalendarGrid>
            <CalendarGridHeader>
              {(day) => <CalendarHeaderCell>{day}</CalendarHeaderCell>}
            </CalendarGridHeader>
            <CalendarGridBody>
              {(date) => <CalendarCell date={date} />}
            </CalendarGridBody>
          </CalendarGrid>
        </RangeCalendar>
      </DatePickerContent>
    </AriaDateRangePicker>
  );
};

export { DatePicker, DatePickerContent, DateRangePicker };
export type { DatePickerProps, DateRangePickerProps };
