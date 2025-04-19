/* Copyright 2024 Marimo. All rights reserved. */

import {
  FormField,
  FormItem,
  FormLabel,
  FormControl,
} from "@/components/ui/form";
import type { UseFormReturn, Path, PathValue } from "react-hook-form";
import type { DataType } from "@/core/kernel/messages";
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { DATA_TYPE_ICON } from "@/components/datasets/icons";
import { DebouncedInput, DebouncedNumberInput } from "@/components/ui/input";
import { SquareFunctionIcon } from "lucide-react";
import { Checkbox } from "@/components/ui/checkbox";
import { cn } from "@/utils/cn";
import { DEFAULT_BIN_VALUE, NONE_GROUP_BY } from "./chart-schemas";
import type { NumberFieldProps } from "@/components/ui/number-field";
import { Button } from "@/components/ui/button";
import { XIcon, PlusIcon } from "lucide-react";
import React from "react";
import type { z } from "zod";
import type { ChartSchema } from "./chart-schemas";
import { SliderComponent } from "@/plugins/impl/SliderPlugin";

export const ColumnSelector = <T extends object>({
  form,
  name,
  columns,
  includeNoneOption = false,
  onValueChange,
}: {
  form: UseFormReturn<T>;
  name: Path<T>;
  columns: Array<{ name: string; type: DataType }>;
  includeNoneOption?: boolean;
  onValueChange?: (fieldName: string, type: DataType) => void;
}) => {
  return (
    <FormField
      control={form.control}
      name={name}
      render={({ field }) => {
        return (
          <FormItem>
            <FormControl>
              <Select
                {...field}
                onValueChange={(value) => {
                  if (value === NONE_GROUP_BY) {
                    form.setValue(name, value as PathValue<T, Path<T>>);
                    return;
                  }

                  const column = columns.find(
                    (column) => column.name === value,
                  );
                  if (column) {
                    form.setValue(name, value as PathValue<T, Path<T>>);
                    const typeFieldName = name.replace(
                      ".field",
                      ".type",
                    ) as Path<T>;
                    form.setValue(
                      typeFieldName,
                      column.type as PathValue<T, Path<T>>,
                    );
                    onValueChange?.(name, column.type);
                  }
                }}
                value={field.value ?? ""}
              >
                <SelectTrigger className="w-2/3">
                  <SelectValue placeholder="Select column" />
                </SelectTrigger>
                <SelectContent>
                  {includeNoneOption && (
                    <SelectItem value={NONE_GROUP_BY}>
                      <div className="flex items-center">
                        <SquareFunctionIcon className="w-3 h-3 mr-2" />
                        None
                      </div>
                    </SelectItem>
                  )}
                  {columns.map((column) => {
                    const DataTypeIcon = DATA_TYPE_ICON[column.type];
                    if (column.name.trim() === "") {
                      return null;
                    }
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
        );
      }}
    />
  );
};

export const SelectField = <T extends object>({
  form,
  name,
  formFieldLabel,
  options,
  defaultValue,
}: {
  form: UseFormReturn<T>;
  name: Path<T>;
  formFieldLabel: string;
  options: Array<{ display: React.ReactNode; value: string }>;
  defaultValue: string;
}) => {
  return (
    <FormField
      control={form.control}
      name={name}
      render={({ field }) => (
        <FormItem className="flex flex-row items-center gap-2">
          <FormLabel>{formFieldLabel}</FormLabel>
          <FormControl>
            <Select
              {...field}
              onValueChange={field.onChange}
              value={field.value ?? defaultValue}
            >
              <SelectTrigger>
                <SelectValue placeholder="Select an option" />
              </SelectTrigger>
              <SelectContent>
                <SelectGroup>
                  {options.map((option) => {
                    return option.value.trim() === "" ? null : (
                      <SelectItem key={option.value} value={option.value}>
                        {option.display}
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

export const InputField = <T extends object>({
  form,
  name,
  formFieldLabel,
}: {
  form: UseFormReturn<T>;
  name: Path<T>;
  formFieldLabel: string;
}) => {
  return (
    <FormField
      control={form.control}
      name={name}
      render={({ field }) => (
        <FormItem>
          <FormLabel>{formFieldLabel}</FormLabel>
          <FormControl>
            <DebouncedInput
              {...field}
              value={field.value ?? ""}
              onValueChange={field.onChange}
              className="w-48 text-xs"
            />
          </FormControl>
        </FormItem>
      )}
    />
  );
};

export const NumberField = <T extends object>({
  form,
  name,
  formFieldLabel,
  className,
  ...props
}: {
  form: UseFormReturn<T>;
  name: Path<T>;
  formFieldLabel: string;
  className?: string;
} & Omit<NumberFieldProps, "value" | "onValueChange">) => {
  return (
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
            />
          </FormControl>
        </FormItem>
      )}
    />
  );
};

export const BooleanField = <T extends object>({
  form,
  name,
  formFieldLabel,
  className,
}: {
  form: UseFormReturn<T>;
  name: Path<T>;
  formFieldLabel: string;
  className?: string;
}) => {
  return (
    <FormField
      control={form.control}
      name={name}
      render={({ field }) => (
        <FormItem className={cn("flex flex-row items-center gap-1", className)}>
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
};

interface SliderFieldProps {
  form: UseFormReturn<z.infer<typeof ChartSchema>>;
  name: Path<z.infer<typeof ChartSchema>>;
  formFieldLabel: string;
  value: number;
  start: number;
  stop: number;
  step?: number;
  className?: string;
}

export const SliderField = ({
  form,
  name,
  formFieldLabel,
  value,
  start,
  stop,
  step,
  className,
  ...props
}: SliderFieldProps) => {
  return (
    <FormField
      control={form.control}
      name={name}
      render={({ field }) => (
        <FormItem className={cn("flex flex-row items-center gap-2", className)}>
          <FormControl>
            <SliderComponent
              {...field}
              {...props}
              value={value}
              setValue={field.onChange}
              start={start}
              stop={stop}
              step={step}
              label={formFieldLabel}
              debounce={false}
              orientation="horizontal"
              showValue={false}
              fullWidth={false}
              steps={null}
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
}: {
  form: UseFormReturn<T>;
  name: Path<T>;
  formFieldLabel: string;
  className?: string;
}) => {
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
