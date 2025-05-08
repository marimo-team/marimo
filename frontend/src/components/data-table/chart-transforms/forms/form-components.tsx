/* Copyright 2024 Marimo. All rights reserved. */

import React from "react";
import { capitalize } from "lodash-es";
import { XIcon, PlusIcon, SquareFunctionIcon } from "lucide-react";
import type { UseFormReturn, Path, PathValue } from "react-hook-form";
import type { z } from "zod";

import type { DataType } from "@/core/kernel/messages";
import type { NumberFieldProps } from "@/components/ui/number-field";
import type { ChartSchema } from "../chart-schemas";

import {
  FormField,
  FormItem,
  FormLabel,
  FormControl,
} from "@/components/ui/form";
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectLabel,
  SelectSeparator,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { DATA_TYPE_ICON } from "@/components/datasets/icons";
import { DebouncedInput, DebouncedNumberInput } from "@/components/ui/input";
import { Checkbox } from "@/components/ui/checkbox";
import { Button } from "@/components/ui/button";
import { cn } from "@/utils/cn";
import { Multiselect } from "@/plugins/impl/MultiselectPlugin";

import { DEFAULT_BIN_VALUE } from "../chart-schemas";
import {
  AGGREGATION_FNS,
  COMBINED_TIME_UNITS,
  NONE_AGGREGATION,
  SELECTABLE_DATA_TYPES,
  SINGLE_TIME_UNITS,
  type TimeUnit,
} from "../types";
import {
  AGGREGATION_TYPE_DESCRIPTIONS,
  AGGREGATION_TYPE_ICON,
  COUNT_FIELD,
  EMPTY_VALUE,
  SCALE_TYPE_DESCRIPTIONS,
  TIME_UNIT_DESCRIPTIONS,
} from "../constants";
import { TypeConverters } from "../chart-spec";
import { IconWithText } from "./chart-components";
import { Slider } from "@/components/ui/slider";

const CLEAR_VALUE = "__clear__";

export interface Field {
  name: string;
  type: DataType;
}

export interface Tooltip {
  field: string;
  type: string;
}

interface BaseFormFieldProps<T extends object> {
  form: UseFormReturn<T>;
  name: Path<T>;
  formFieldLabel: string;
  className?: string;
}

export const ColumnSelector = <T extends object>({
  form,
  name,
  columns,
  onValueChange,
  includeCountField = true,
}: {
  form: UseFormReturn<T>;
  name: Path<T>;
  columns: Array<{ name: string; type: DataType }>;
  onValueChange?: (fieldName: string, type: DataType | undefined) => void;
  includeCountField?: boolean;
}) => {
  type AnyPath = Path<T>;
  type AnyPathValue = PathValue<T, Path<T>>;
  const ANY_VALUE = EMPTY_VALUE as AnyPathValue;
  const pathType = name.replace(".field", ".type") as AnyPath;
  const pathSelectedDataType = name.replace(
    ".field",
    ".selectedDataType",
  ) as AnyPath;

  const clear = () => {
    form.setValue(name, ANY_VALUE);
    form.setValue(pathType, ANY_VALUE);
    form.setValue(pathSelectedDataType, ANY_VALUE);
    onValueChange?.(EMPTY_VALUE, undefined);
  };

  return (
    <FormField
      control={form.control}
      name={name}
      render={({ field }) => (
        <FormItem>
          <FormControl>
            <Select
              {...field}
              onValueChange={(value) => {
                // Handle clear
                if (value === CLEAR_VALUE) {
                  clear();
                  return;
                }

                // Handle count
                if (value === COUNT_FIELD) {
                  form.setValue(name, value as AnyPathValue);
                  form.setValue(pathType, ANY_VALUE);
                  form.setValue(pathSelectedDataType, ANY_VALUE);
                  onValueChange?.(name, "number");
                  return;
                }

                // Handle column selection
                const column = columns.find((column) => column.name === value);
                if (column) {
                  form.setValue(name, value as AnyPathValue);
                  form.setValue(pathType, column.type as AnyPathValue);
                  form.setValue(
                    pathSelectedDataType,
                    TypeConverters.toSelectableDataType(
                      column.type,
                    ) as AnyPathValue,
                  );
                  onValueChange?.(name, column.type);
                }
              }}
              value={field.value ?? EMPTY_VALUE}
            >
              <SelectTrigger
                className="w-40 truncate"
                onClear={field.value ? clear : undefined}
              >
                <SelectValue placeholder="Select column" />
              </SelectTrigger>
              <SelectContent>
                {field.value && (
                  <SelectItem value={CLEAR_VALUE}>
                    <div className="flex items-center truncate">
                      <XIcon className="w-3 h-3 mr-2" />
                      Clear
                    </div>
                  </SelectItem>
                )}
                {includeCountField && (
                  <>
                    <SelectItem key={COUNT_FIELD} value={COUNT_FIELD}>
                      <div className="flex items-center truncate">
                        <SquareFunctionIcon className="w-3 h-3 mr-2" />
                        Count of records
                      </div>
                    </SelectItem>
                    <SelectSeparator />
                  </>
                )}
                {columns.map((column) => {
                  if (column.name.trim() === EMPTY_VALUE) {
                    return null;
                  }
                  const DataTypeIcon = DATA_TYPE_ICON[column.type];
                  return (
                    <SelectItem key={column.name} value={column.name}>
                      <div className="flex items-center truncate">
                        <DataTypeIcon className="w-3 h-3 mr-2" />
                        {column.name}
                      </div>
                    </SelectItem>
                  );
                })}
              </SelectContent>
            </Select>
          </FormControl>
        </FormItem>
      )}
    />
  );
};

export const SelectField = <T extends object>({
  form,
  name,
  formFieldLabel,
  options,
  defaultValue,
}: BaseFormFieldProps<T> & {
  options: Array<{ display: React.ReactNode; value: string }>;
  defaultValue: string;
}) => (
  <FormField
    control={form.control}
    name={name}
    render={({ field }) => (
      <FormItem className="flex flex-row items-center justify-between">
        <FormLabel>{formFieldLabel}</FormLabel>
        <FormControl>
          <Select
            {...field}
            onValueChange={field.onChange}
            value={field.value ?? defaultValue}
          >
            <SelectTrigger className="truncate">
              <SelectValue placeholder="Select an option" />
            </SelectTrigger>
            <SelectContent>
              <SelectGroup>
                {options
                  .filter((option) => option.value !== EMPTY_VALUE)
                  .map((option) => (
                    <SelectItem key={option.value} value={option.value}>
                      {option.display}
                    </SelectItem>
                  ))}
              </SelectGroup>
            </SelectContent>
          </Select>
        </FormControl>
      </FormItem>
    )}
  />
);

export const InputField = <T extends object>({
  form,
  name,
  formFieldLabel,
}: BaseFormFieldProps<T>) => (
  <FormField
    control={form.control}
    name={name}
    render={({ field }) => (
      <FormItem className="flex flex-row gap-2 items-center">
        <FormLabel>{formFieldLabel}</FormLabel>
        <FormControl>
          <DebouncedInput
            {...field}
            value={field.value ?? EMPTY_VALUE}
            onValueChange={field.onChange}
            className="text-xs h-5"
          />
        </FormControl>
      </FormItem>
    )}
  />
);

export const NumberField = <T extends object>({
  form,
  name,
  formFieldLabel,
  className,
  ...props
}: BaseFormFieldProps<T> &
  Omit<NumberFieldProps, "value" | "onValueChange">) => (
  <FormField
    control={form.control}
    name={name}
    render={({ field }) => (
      <FormItem className={cn("flex flex-row items-center gap-2", className)}>
        <FormLabel className="whitespace-nowrap">{formFieldLabel}</FormLabel>
        <FormControl>
          <DebouncedNumberInput
            {...field}
            value={field.value ?? DEFAULT_BIN_VALUE}
            onValueChange={field.onChange}
            aria-label={formFieldLabel}
            {...props}
            className="w-16"
          />
        </FormControl>
      </FormItem>
    )}
  />
);

export const BooleanField = <T extends object>({
  form,
  name,
  formFieldLabel,
  className,
}: BaseFormFieldProps<T>) => (
  <FormField
    control={form.control}
    name={name}
    render={({ field }) => (
      <FormItem className={cn("flex flex-row items-center gap-2", className)}>
        <FormLabel>{formFieldLabel}</FormLabel>
        <FormControl>
          <Checkbox
            checked={field.value}
            onCheckedChange={field.onChange}
            className="w-4 h-4"
          />
        </FormControl>
      </FormItem>
    )}
  />
);

interface SliderFieldProps<T extends object> extends BaseFormFieldProps<T> {
  value: number;
  start: number;
  stop: number;
  step?: number;
}

export const SliderField = <T extends object>({
  form,
  name,
  formFieldLabel,
  value,
  start,
  stop,
  step,
  className,
  ...props
}: SliderFieldProps<T>) => {
  const [internalValue, setInternalValue] = React.useState(value);

  // Update internal value on prop change
  React.useEffect(() => {
    setInternalValue(value);
  }, [value]);

  return (
    <FormField
      control={form.control}
      name={name}
      render={({ field }) => (
        <FormItem
          className={cn("flex flex-row items-center gap-2 w-1/2", className)}
        >
          <FormLabel>{formFieldLabel}</FormLabel>
          <FormControl>
            <Slider
              {...field}
              {...props}
              id={name}
              className="relative flex items-center select-none"
              value={[internalValue]}
              min={start}
              max={stop}
              step={step}
              // Triggered on slider drag
              onValueChange={([nextValue]) => {
                setInternalValue(nextValue);
                field.onChange(nextValue);
              }}
              // Triggered on mouse up
              onValueCommit={([nextValue]) => {
                field.onChange(nextValue);
                form.setValue(name, nextValue as PathValue<T, Path<T>>);
              }}
              valueMap={(value) => value}
            />
          </FormControl>
        </FormItem>
      )}
    />
  );
};

export const ColorArrayField = <T extends object>({
  form,
  name,
  formFieldLabel,
  className,
}: BaseFormFieldProps<T>) => {
  const formValue = form.watch(name);
  const [colors, setColors] = React.useState<string[]>(formValue ?? []);

  const addColor = () => {
    const newColors = [...colors, "#000000"];
    setColors(newColors);
    form.setValue(name, newColors as PathValue<T, Path<T>>);
  };

  const removeColor = (index: number) => {
    const newColors = colors.filter((_, i) => i !== index);
    setColors(newColors);
    form.setValue(name, newColors as PathValue<T, Path<T>>);
  };

  const updateColor = (index: number, value: string) => {
    const newColors = [...colors];
    newColors[index] = value;
    setColors(newColors);
    form.setValue(name, newColors as PathValue<T, Path<T>>);
  };

  return (
    <FormField
      control={form.control}
      name={name}
      render={() => (
        <FormItem className={cn("flex flex-col gap-2", className)}>
          <FormLabel>{formFieldLabel}</FormLabel>
          <div className="flex flex-col gap-2">
            {colors.map((color, index) => (
              <div key={index} className="flex items-center gap-2">
                <input
                  type="color"
                  value={color}
                  onChange={(e) => updateColor(index, e.target.value)}
                  className="w-4 h-4 rounded cursor-pointer"
                />
                <span className="text-xs text-muted-foreground font-mono">
                  {color}
                </span>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => removeColor(index)}
                  className="h-4 w-4 p-0"
                >
                  <XIcon className="h-2 w-2" />
                </Button>
              </div>
            ))}
            <Button
              variant="outline"
              size="sm"
              onClick={addColor}
              className="w-fit h-6 text-xs"
            >
              <PlusIcon className="h-3 w-3 mr-1" />
              Add Color
            </Button>
          </div>
        </FormItem>
      )}
    />
  );
};

export const TimeUnitSelect = <T extends object>({
  form,
  name,
  formFieldLabel,
}: BaseFormFieldProps<T>) => {
  const clear = () => {
    form.setValue(name, EMPTY_VALUE as PathValue<T, Path<T>>);
  };

  const renderTimeUnit = (unit: TimeUnit) => {
    const [label, description] = TIME_UNIT_DESCRIPTIONS[unit];
    return (
      <SelectItem
        key={unit}
        value={unit}
        className="flex flex-row"
        subtitle={
          <span className="text-xs text-muted-foreground ml-auto">
            {description}
          </span>
        }
      >
        {label}
      </SelectItem>
    );
  };
  return (
    <FormField
      control={form.control}
      name={name}
      render={({ field }) => (
        <FormItem className="flex flex-row items-center justify-between w-full">
          <FormLabel>{formFieldLabel}</FormLabel>
          <FormControl>
            <Select
              {...field}
              onValueChange={(value) => {
                if (value === CLEAR_VALUE) {
                  clear();
                } else {
                  field.onChange(value);
                }
              }}
              value={field.value}
            >
              <SelectTrigger onClear={field.value ? clear : undefined}>
                <SelectValue placeholder="Select unit" />
              </SelectTrigger>
              <SelectContent className="w-72">
                {field.value && (
                  <>
                    <SelectItem value={CLEAR_VALUE}>
                      <div className="flex items-center truncate">
                        <XIcon className="w-3 h-3 mr-2" />
                        Clear
                      </div>
                    </SelectItem>
                    <SelectSeparator />
                  </>
                )}
                <SelectGroup>
                  {COMBINED_TIME_UNITS.map(renderTimeUnit)}
                  <SelectSeparator />
                  {SINGLE_TIME_UNITS.map(renderTimeUnit)}
                </SelectGroup>
              </SelectContent>
            </Select>
          </FormControl>
        </FormItem>
      )}
    />
  );
};

export const DataTypeSelect = <T extends object>({
  form,
  name,
  formFieldLabel,
  defaultValue,
  onValueChange,
}: BaseFormFieldProps<T> & {
  defaultValue: string;
  onValueChange?: (value: string) => void;
}) => {
  const [isOpen, setIsOpen] = React.useState(false);

  return (
    <FormField
      control={form.control}
      name={name}
      render={({ field }) => (
        <FormItem className="flex flex-row items-center justify-between w-full">
          <FormLabel>{formFieldLabel}</FormLabel>
          <FormControl>
            <Select
              {...field}
              onValueChange={(value) => {
                field.onChange(value);
                onValueChange?.(value);
              }}
              value={field.value ?? defaultValue}
              open={isOpen}
              onOpenChange={setIsOpen}
            >
              <SelectTrigger>
                <SelectValue placeholder="Select an option" />
              </SelectTrigger>
              <SelectContent>
                <SelectGroup>
                  {SELECTABLE_DATA_TYPES.map((type) => {
                    const Icon = DATA_TYPE_ICON[type];
                    return (
                      <SelectItem
                        key={type}
                        value={type}
                        className="flex flex-col items-start justify-center"
                        subtitle={
                          isOpen && (
                            <span className="text-xs text-muted-foreground">
                              {SCALE_TYPE_DESCRIPTIONS[type]}
                            </span>
                          )
                        }
                      >
                        <IconWithText Icon={Icon} text={capitalize(type)} />
                      </SelectItem>
                    );
                  })}
                </SelectGroup>
              </SelectContent>
            </Select>
          </FormControl>
        </FormItem>
      )}
    />
  );
};

export const AggregationSelect = <T extends object>({
  form,
  name,
}: { form: UseFormReturn<T>; name: Path<T> }) => (
  <FormField
    control={form.control}
    name={name}
    render={({ field }) => (
      <FormItem>
        <FormControl>
          <Select
            {...field}
            value={field.value ?? NONE_AGGREGATION}
            onValueChange={field.onChange}
          >
            <SelectTrigger variant="ghost">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectGroup>
                <SelectLabel>Aggregation</SelectLabel>
                {AGGREGATION_FNS.map((agg) => {
                  const Icon = AGGREGATION_TYPE_ICON[agg];
                  return (
                    <SelectItem
                      key={agg}
                      value={agg}
                      className="flex flex-col items-start justify-center"
                      subtitle={
                        <span className="text-xs text-muted-foreground pr-10">
                          {AGGREGATION_TYPE_DESCRIPTIONS[agg]}
                        </span>
                      }
                    >
                      <div className="flex items-center">
                        <Icon className="w-3 h-3 mr-2" />
                        {capitalize(agg)}
                      </div>
                    </SelectItem>
                  );
                })}
              </SelectGroup>
            </SelectContent>
          </Select>
        </FormControl>
      </FormItem>
    )}
  />
);

export const TooltipSelect = <T extends z.infer<typeof ChartSchema>>({
  form,
  name,
  formFieldLabel,
  fields,
  saveFunction,
}: {
  form: UseFormReturn<T>;
  formFieldLabel?: string;
  name: Path<T>;
  fields: Field[];
  saveFunction: () => void;
}) => (
  <FormField
    control={form.control}
    name={name}
    render={({ field }) => {
      const tooltips = field.value as Tooltip[] | undefined;
      return (
        <FormItem className="flex flex-row gap-2 items-center">
          {formFieldLabel && <FormLabel>{formFieldLabel}</FormLabel>}
          <FormControl>
            <Multiselect
              options={fields?.map((field) => field.name) ?? []}
              value={tooltips?.map((t) => t.field) ?? []}
              setValue={(values) => {
                const selectedValues =
                  typeof values === "function" ? values([]) : values;

                const tooltipObjects = selectedValues.map((fieldName) => {
                  const fieldType = fields?.find(
                    (f) => f.name === fieldName,
                  )?.type;

                  return {
                    field: fieldName,
                    type: fieldType ?? "string",
                  };
                });

                field.onChange(tooltipObjects);
                saveFunction();
              }}
              label={null}
              fullWidth={false}
            />
          </FormControl>
        </FormItem>
      );
    }}
  />
);
