/* Copyright 2024 Marimo. All rights reserved. */

import React from "react";
import { capitalize } from "lodash-es";
import {
  XIcon,
  PlusIcon,
  SquareFunctionIcon,
  ArrowUpWideNarrowIcon,
  ArrowDownWideNarrowIcon,
} from "lucide-react";
import { type Path, useFormContext, useWatch } from "react-hook-form";

import type { DataType } from "@/core/kernel/messages";

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

import {
  AGGREGATION_FNS,
  COMBINED_TIME_UNITS,
  NONE_AGGREGATION,
  SELECTABLE_DATA_TYPES,
  type SelectableDataType,
  SINGLE_TIME_UNITS,
  SORT_TYPES,
  STRING_AGGREGATION_FNS,
  BIN_AGGREGATION,
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
import { Slider } from "@/components/ui/slider";
import { IconWithText } from "./layouts";
import { useChartFormContext } from "../context";
import type { NumberFieldProps } from "@/components/ui/number-field";
import { convertDataTypeToSelectable } from "../chart-spec/types";
import type { BinSchema, ChartSchema, ChartSchemaType } from "../schemas";
import type { z } from "zod";

const CLEAR_VALUE = "__clear__";

export type FieldName = Path<z.infer<typeof ChartSchema>>;

export interface Field {
  name: string;
  type: DataType;
}

export interface Tooltip {
  field: string;
  type: DataType;
  bin?: z.infer<typeof BinSchema>;
}

export const ColumnSelector = ({
  fieldName,
  columns,
  onValueChange,
  includeCountField = true,
}: {
  fieldName: FieldName;
  columns: Array<{ name: string; type: DataType }>;
  onValueChange?: (fieldName: string, type: DataType | undefined) => void;
  includeCountField?: boolean;
}) => {
  const form = useFormContext();
  const pathType = fieldName.replace(".field", ".type");
  const pathSelectedDataType = fieldName.replace(".field", ".selectedDataType");

  const clear = () => {
    form.setValue(fieldName, EMPTY_VALUE);
    form.setValue(pathType, EMPTY_VALUE);
    form.setValue(pathSelectedDataType, EMPTY_VALUE);
    onValueChange?.(EMPTY_VALUE, undefined);
  };

  return (
    <FormField
      control={form.control}
      name={fieldName}
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
                  form.setValue(fieldName, value);
                  form.setValue(pathType, EMPTY_VALUE);
                  form.setValue(pathSelectedDataType, EMPTY_VALUE);
                  onValueChange?.(fieldName, "number");
                  return;
                }

                // Handle column selection
                const column = columns.find((column) => column.name === value);
                if (column) {
                  form.setValue(fieldName, value);
                  form.setValue(pathType, column.type);
                  form.setValue(
                    pathSelectedDataType,
                    convertDataTypeToSelectable(column.type),
                  );
                  onValueChange?.(fieldName, column.type);
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

export const SelectField = ({
  fieldName,
  label,
  options,
  defaultValue,
}: {
  fieldName: FieldName;
  label: string;
  options: Array<{ display: React.ReactNode; value: string }>;
  defaultValue: string;
}) => {
  const form = useFormContext();

  return (
    <FormField
      control={form.control}
      name={fieldName}
      render={({ field }) => (
        <FormItem className="flex flex-row items-center justify-between">
          <FormLabel>{label}</FormLabel>
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
};

export const InputField = ({
  fieldName,
  label,
}: {
  fieldName: FieldName;
  label: string;
}) => {
  const form = useFormContext();
  return (
    <FormField
      control={form.control}
      name={fieldName}
      render={({ field }) => (
        <FormItem className="flex flex-row gap-2 items-center">
          <FormLabel>{label}</FormLabel>
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
};

export const NumberField = ({
  fieldName,
  label,
  className,
  inputClassName,
  isDisabled,
  ...props
}: NumberFieldProps & {
  fieldName: FieldName;
  label: string;
  className?: string;
  inputClassName?: string;
  isDisabled?: boolean;
}) => {
  const form = useFormContext();
  return (
    <FormField
      control={form.control}
      name={fieldName}
      render={({ field }) => (
        <FormItem className={cn("flex flex-row items-center gap-2", className)}>
          <FormLabel className="whitespace-nowrap">{label}</FormLabel>
          <FormControl>
            <DebouncedNumberInput
              {...field}
              value={field.value}
              onValueChange={field.onChange}
              aria-label={label}
              className={cn("w-16", inputClassName)}
              isDisabled={isDisabled}
              minValue={0}
              {...props}
            />
          </FormControl>
        </FormItem>
      )}
    />
  );
};

export const BooleanField = ({
  fieldName,
  label,
  className,
  defaultValue,
}: {
  fieldName: FieldName;
  label: string;
  className?: string;
  defaultValue?: boolean;
}) => {
  const form = useFormContext();
  return (
    <FormField
      control={form.control}
      name={fieldName}
      render={({ field }) => (
        <FormItem className={cn("flex flex-row items-center gap-2", className)}>
          <FormLabel>{label}</FormLabel>
          <FormControl>
            <Checkbox
              checked={field.value ?? defaultValue ?? false}
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
  fieldName: FieldName;
  label: string;
  className?: string;
  value: number;
  start: number;
  stop: number;
  step?: number;
}

export const SliderField = ({
  fieldName,
  label,
  value,
  start,
  stop,
  step,
  className,
}: SliderFieldProps) => {
  const [internalValue, setInternalValue] = React.useState(value);
  const form = useFormContext();

  // Update internal value on prop change
  React.useEffect(() => {
    setInternalValue(value);
  }, [value]);

  return (
    <FormField
      control={form.control}
      name={fieldName}
      render={({ field }) => (
        <FormItem
          className={cn("flex flex-row items-center gap-2 w-1/2", className)}
        >
          <FormLabel>{label}</FormLabel>
          <FormControl>
            <Slider
              {...field}
              id={fieldName}
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
                form.setValue(fieldName, nextValue);
              }}
              valueMap={(value) => value}
            />
          </FormControl>
        </FormItem>
      )}
    />
  );
};

export const ColorArrayField = ({
  fieldName,
  label,
  className,
}: {
  fieldName: FieldName;
  label: string;
  className?: string;
}) => {
  const form = useFormContext();
  const formValue = form.watch(fieldName);
  const [colors, setColors] = React.useState<string[]>(formValue ?? []);

  const addColor = () => {
    const newColors = [...colors, "#000000"];
    setColors(newColors);
    form.setValue(fieldName, newColors);
  };

  const removeColor = (index: number) => {
    const newColors = colors.filter((_, i) => i !== index);
    setColors(newColors);
    form.setValue(fieldName, newColors);
  };

  const updateColor = (index: number, value: string) => {
    const newColors = [...colors];
    newColors[index] = value;
    setColors(newColors);
    form.setValue(fieldName, newColors);
  };

  return (
    <FormField
      control={form.control}
      name={fieldName}
      render={() => (
        <FormItem className={cn("flex flex-col gap-2", className)}>
          <FormLabel>{label}</FormLabel>
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

export const TimeUnitSelect = ({
  fieldName,
  label,
}: {
  fieldName: FieldName;
  label: string;
}) => {
  const form = useFormContext();
  const clear = () => {
    form.setValue(fieldName, EMPTY_VALUE);
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
      name={fieldName}
      render={({ field }) => (
        <FormItem className="flex flex-row items-center justify-between w-full">
          <FormLabel>{label}</FormLabel>
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

export const DataTypeSelect = ({
  fieldName,
  label,
  defaultValue,
  onValueChange,
}: {
  fieldName: FieldName;
  label: string;
  defaultValue: string;
  onValueChange?: (value: string) => void;
}) => {
  const [isOpen, setIsOpen] = React.useState(false);
  const form = useFormContext();

  return (
    <FormField
      control={form.control}
      name={fieldName}
      render={({ field }) => (
        <FormItem className="flex flex-row items-center justify-between w-full">
          <FormLabel>{label}</FormLabel>
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

export const AggregationSelect = ({
  fieldName,
  selectedDataType,
  binFieldName,
}: {
  fieldName: FieldName;
  selectedDataType: SelectableDataType;
  binFieldName: FieldName;
}) => {
  const form = useFormContext();
  const availableAggregations =
    selectedDataType === "string" ? STRING_AGGREGATION_FNS : AGGREGATION_FNS;

  const renderSubtitle = (text: string) => {
    return <span className="text-xs text-muted-foreground pr-10">{text}</span>;
  };

  const renderSelectItem = (
    value: string,
    Icon: React.ElementType,
    subtitle: React.ReactNode,
  ) => {
    return (
      <SelectItem
        key={value}
        value={value}
        className="flex flex-col items-start justify-center"
        subtitle={subtitle}
      >
        <div className="flex items-center">
          <Icon className="w-3 h-3 mr-2" />
          {capitalize(value)}
        </div>
      </SelectItem>
    );
  };

  const handleFieldChange = (
    value: string,
    previousValue: string,
    onChange: (value: string) => void,
  ) => {
    // Special handling for binning, as this is not a valid aggregation
    if (value === BIN_AGGREGATION) {
      form.setValue(binFieldName, true);
    } else if (previousValue === BIN_AGGREGATION) {
      // Otherwise, unset the bin field
      form.setValue(binFieldName, false);
    }

    onChange(value);
  };

  return (
    <FormField
      control={form.control}
      name={fieldName}
      render={({ field }) => (
        <FormItem>
          <FormControl>
            <Select
              {...field}
              value={(field.value ?? NONE_AGGREGATION).toString()}
              onValueChange={(value) => {
                handleFieldChange(value, field.value, field.onChange);
              }}
            >
              <SelectTrigger variant="ghost">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectGroup>
                  <SelectLabel>Aggregation</SelectLabel>
                  {availableAggregations.map((agg) => {
                    const Icon = AGGREGATION_TYPE_ICON[agg];
                    const subtitle = renderSubtitle(
                      AGGREGATION_TYPE_DESCRIPTIONS[agg],
                    );
                    const selectItem = renderSelectItem(agg, Icon, subtitle);
                    if (agg === BIN_AGGREGATION) {
                      return (
                        <>
                          <SelectSeparator />
                          {selectItem}
                        </>
                      );
                    }
                    return selectItem;
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

export const TooltipSelect = ({
  fieldName,
  saveFunction,
}: {
  fieldName: FieldName;
  saveFunction: () => void;
}) => {
  const form = useFormContext();
  const { fields } = useChartFormContext();

  const createTooltip = (name: string, fields: Field[]) => {
    const field = fields.find((f) => f.name === name);
    return {
      field: name,
      type: field?.type ?? "string",
    };
  };

  return (
    <FormField
      control={form.control}
      name={fieldName}
      render={({ field }) => {
        const tooltips = field.value as Tooltip[] | undefined;
        const values = tooltips?.map((t) => t.field) ?? [];

        return (
          <FormItem>
            <FormControl>
              <Multiselect
                options={fields?.map((field) => field.name) ?? []}
                value={values}
                setValue={(values) => {
                  const selectedValues =
                    typeof values === "function" ? values([]) : values;

                  const tooltipObjects = selectedValues.map((fieldName) => {
                    return createTooltip(fieldName, fields);
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
};

export const SortField = ({
  fieldName,
  label,
  defaultValue,
}: {
  fieldName: FieldName;
  label: string;
  defaultValue?: string;
}) => {
  return (
    <SelectField
      fieldName={fieldName}
      label={label}
      options={SORT_TYPES.map((type) => ({
        display: (
          <IconWithText
            Icon={
              type === "ascending"
                ? ArrowUpWideNarrowIcon
                : ArrowDownWideNarrowIcon
            }
            text={capitalize(type)}
          />
        ),
        value: type,
      }))}
      defaultValue={defaultValue ?? "ascending"}
    />
  );
};

export const BinFields: React.FC<{
  fieldName: "xAxis" | "yAxis" | "color";
}> = ({ fieldName }) => {
  const form = useFormContext<ChartSchemaType>();
  const formValues = useWatch({ control: form.control });
  const isBinned = formValues[fieldName]?.bin?.binned;

  if (!isBinned) {
    return null;
  }

  const hasStep = !Number.isNaN(formValues[fieldName]?.bin?.step);

  return (
    <div className="flex flex-row justify-between">
      <NumberField
        fieldName={`${fieldName}.bin.step`}
        label="Bin step"
        inputClassName="w-14"
        placeholder="0.5"
      />
      <NumberField
        fieldName={`${fieldName}.bin.maxbins`}
        label="Max bins"
        inputClassName="w-14"
        isDisabled={hasStep}
        placeholder="10"
      />
    </div>
  );
};
