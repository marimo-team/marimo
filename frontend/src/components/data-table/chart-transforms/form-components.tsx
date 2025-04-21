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
  SelectLabel,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { DATA_TYPE_ICON } from "@/components/datasets/icons";
import { DebouncedInput, DebouncedNumberInput } from "@/components/ui/input";
import { type LucideProps, SquareFunctionIcon } from "lucide-react";
import { Checkbox } from "@/components/ui/checkbox";
import { cn } from "@/utils/cn";
import {
  DEFAULT_AGGREGATION,
  DEFAULT_BIN_VALUE,
  NONE_GROUP_BY,
  SCALE_TYPES,
} from "./chart-schemas";
import type { NumberFieldProps } from "@/components/ui/number-field";
import { Button } from "@/components/ui/button";
import { AGGREGATION_TYPE_ICON } from "./constants";
import { XIcon, PlusIcon } from "lucide-react";
import React from "react";
import type { z } from "zod";
import type { ChartSchema, ScaleType } from "./chart-schemas";
import { SliderComponent } from "@/plugins/impl/SliderPlugin";
import { SCALE_TYPE_DESCRIPTIONS } from "./constants";
import { capitalize } from "lodash-es";
import { AGGREGATION_FNS } from "@/plugins/impl/data-frames/types";
import { Multiselect } from "@/plugins/impl/MultiselectPlugin";
import { inferScaleType } from "./chart-spec";

export interface Field {
  name: string;
  type: DataType;
}

export const ColumnSelector = <T extends object>({
  form,
  name,
  columns,
  onValueChange,
}: {
  form: UseFormReturn<T>;
  name: Path<T>;
  columns: Array<{ name: string; type: DataType }>;
  onValueChange?: (fieldName: string, type: DataType | undefined) => void;
}) => {
  const clear = () => {
    form.setValue(name, "" as PathValue<T, Path<T>>);
    form.setValue(
      name.replace(".field", ".type") as Path<T>,
      "" as PathValue<T, Path<T>>,
    );
    form.setValue(
      name.replace(".field", ".scaleType") as Path<T>,
      "" as PathValue<T, Path<T>>,
    );
    onValueChange?.("", undefined);
  };

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

                    // Update the type field
                    form.setValue(
                      name.replace(".field", ".type") as Path<T>,
                      column.type as PathValue<T, Path<T>>,
                    );

                    // Update the scale type field
                    // Whenever user changes the column, we infer the scale type
                    form.setValue(
                      name.replace(".field", ".scaleType") as Path<T>,
                      inferScaleType(column.type) as PathValue<T, Path<T>>,
                    );

                    onValueChange?.(name, column.type);
                  }
                }}
                value={field.value ?? ""}
              >
                <SelectTrigger
                  className="w-40"
                  onClear={field.value ? clear : undefined}
                >
                  <SelectValue placeholder="Select column" />
                </SelectTrigger>
                <SelectContent>
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
        <FormItem className="flex flex-row gap-2 items-center">
          <FormLabel>{formFieldLabel}</FormLabel>
          <FormControl>
            <DebouncedInput
              {...field}
              value={field.value ?? ""}
              onValueChange={field.onChange}
              className="text-xs h-5"
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
              setValue={(value) => {
                field.onChange(value);
                form.setValue(name, value as PathValue<T, Path<T>>);
              }}
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

export const ScaleTypeSelect = <T extends object>({
  form,
  name,
  formFieldLabel,
  defaultValue,
}: {
  form: UseFormReturn<T>;
  name: Path<T>;
  formFieldLabel: string;
  defaultValue: string;
}) => {
  const [isOpen, setIsOpen] = React.useState(false);

  return (
    <FormField
      control={form.control}
      name={name}
      render={({ field }) => (
        <FormItem className="flex flex-row items-center gap-2 w-full">
          <FormLabel>{formFieldLabel}</FormLabel>
          <FormControl>
            <Select
              {...field}
              onValueChange={field.onChange}
              value={field.value ?? defaultValue}
              open={isOpen}
              onOpenChange={setIsOpen}
            >
              <SelectTrigger>
                <SelectValue placeholder="Select an option" />
              </SelectTrigger>
              <SelectContent>
                <SelectGroup>
                  {SCALE_TYPES.map((type) => {
                    const Icon = DATA_TYPE_ICON[type];
                    return (
                      <SelectItem
                        key={type}
                        value={type}
                        className="flex flex-col items-start justify-center"
                        subtitle={
                          isOpen && (
                            <span className="text-xs text-muted-foreground">
                              {SCALE_TYPE_DESCRIPTIONS[type as ScaleType]}
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
}: { form: UseFormReturn<T>; name: Path<T> }) => {
  return (
    <FormField
      control={form.control}
      name={name}
      render={({ field }) => (
        <FormItem>
          <FormControl>
            <Select
              {...field}
              value={field.value ?? DEFAULT_AGGREGATION}
              onValueChange={field.onChange}
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectGroup>
                  <SelectLabel>Aggregation</SelectLabel>
                  <SelectItem value={DEFAULT_AGGREGATION}>
                    <div className="flex items-center">
                      <SquareFunctionIcon className="w-3 h-3 mr-2" />
                      {capitalize(DEFAULT_AGGREGATION)}
                    </div>
                  </SelectItem>
                  {AGGREGATION_FNS.map((agg) => {
                    const Icon = AGGREGATION_TYPE_ICON[agg];
                    return (
                      <SelectItem key={agg} value={agg}>
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
};

interface Tooltip {
  field: string;
  type: string;
}

export const TooltipSelect = <T extends z.infer<typeof ChartSchema>>({
  form,
  name,
  formFieldLabel,
  fields,
  saveFunction,
}: {
  form: UseFormReturn<T>;
  name: Path<T>;
  formFieldLabel: string;
  fields: Field[];
  saveFunction: () => void;
}) => {
  return (
    <FormField
      control={form.control}
      name={name}
      render={({ field }) => {
        const tooltips = field.value as Tooltip[] | undefined;
        return (
          <FormItem>
            <FormControl>
              <Multiselect
                options={fields?.map((field) => field.name) ?? []}
                value={tooltips?.map((t) => t.field) ?? []}
                setValue={(values) => {
                  const selectedValues =
                    typeof values === "function" ? values([]) : values;

                  // find the field types and form objects
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
                  // Multiselect doesn't trigger onChange, so we need to save the form manually
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
};

export const IconWithText: React.FC<{
  Icon: React.ForwardRefExoticComponent<
    Omit<LucideProps, "ref"> & React.RefAttributes<SVGSVGElement>
  >;
  text: string;
}> = ({ Icon, text }) => {
  return (
    <div className="flex items-center">
      <Icon className="w-3 h-3 mr-2" />
      <span>{text}</span>
    </div>
  );
};

export const Title: React.FC<{ text: string }> = ({ text }) => {
  return <span className="font-semibold my-0">{text}</span>;
};
