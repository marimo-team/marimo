/* Copyright 2024 Marimo. All rights reserved. */

import type { LucideProps } from "lucide-react";
import { cn } from "@/utils/cn";
import {
  ArrowDownWideNarrowIcon,
  ArrowUpWideNarrowIcon,
  ChevronDown,
  Loader2,
} from "lucide-react";
import { capitalize } from "lodash-es";
import * as SelectPrimitive from "@radix-ui/react-select";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectValue,
} from "@/components/ui/select";
import {
  CHART_TYPE_ICON,
  CHART_TYPES,
  COUNT_FIELD,
  type ChartType,
} from "./constants";
import { ErrorBanner } from "@/plugins/impl/common/error-banner";
import { buttonVariants } from "@/components/ui/button";
import { type UseFormReturn, useWatch } from "react-hook-form";
import type { z } from "zod";
import type { ChartSchema } from "./chart-schemas";
import { FieldValidators, TypeConverters } from "./chart-spec";
import {
  ColumnSelector,
  AggregationSelect,
  DataTypeSelect,
  TimeUnitSelect,
  SelectField,
  BooleanField,
  type Field,
} from "./form-components";
import { SORT_TYPES } from "./types";

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

export const TabContainer: React.FC<{
  className?: string;
  children: React.ReactNode;
}> = ({ children, className }) => {
  return <div className={cn("flex flex-col gap-2", className)}>{children}</div>;
};

export const ChartLoadingState: React.FC = () => (
  <div className="flex items-center gap-2 justify-center h-full w-full">
    <Loader2 className="w-10 h-10 animate-spin" strokeWidth={1} />
    <span>Loading chart...</span>
  </div>
);

export const ChartErrorState: React.FC<{ error: Error }> = ({ error }) => (
  <div className="flex items-center justify-center h-full w-full">
    <ErrorBanner error={error} />
  </div>
);

export const ChartTypeSelect: React.FC<{
  value: ChartType;
  onValueChange: (value: ChartType) => void;
}> = ({ value, onValueChange }) => {
  return (
    <Select value={value} onValueChange={onValueChange}>
      <div className="flex flex-row gap-2 items-center">
        <SelectPrimitive.Trigger
          className={buttonVariants({
            variant: "outline",
            className: "user-select-none w-full justify-between px-3",
          })}
        >
          <SelectValue />
          <SelectPrimitive.Icon asChild={true}>
            <ChevronDown className="h-4 w-4 opacity-50" />
          </SelectPrimitive.Icon>
        </SelectPrimitive.Trigger>
        <SelectContent>
          {CHART_TYPES.map((chartType) => (
            <ChartSelectItem key={chartType} chartType={chartType} />
          ))}
        </SelectContent>
      </div>
    </Select>
  );
};

const ChartSelectItem: React.FC<{ chartType: ChartType }> = ({ chartType }) => {
  const Icon = CHART_TYPE_ICON[chartType];
  return (
    <SelectItem value={chartType} className="gap-2">
      <div className="flex items-center">
        <Icon className="w-4 h-4 mr-2" />
        {capitalize(chartType)}
      </div>
    </SelectItem>
  );
};

export const XAxis: React.FC<{
  form: UseFormReturn<z.infer<typeof ChartSchema>>;
  fields: Field[];
}> = ({ form, fields }) => {
  const formValues = useWatch({ control: form.control });
  const xColumn = formValues.general?.xColumn;
  const xColumnExists = FieldValidators.exists(xColumn?.field);

  const inferredXDataType = xColumn?.type
    ? TypeConverters.toSelectableDataType(xColumn.type)
    : "string";

  const selectedXDataType = xColumn?.selectedDataType || inferredXDataType;
  const isXCountField = xColumn?.field === COUNT_FIELD;

  const shouldShowXAggregation =
    xColumnExists && selectedXDataType !== "temporal" && !isXCountField;

  const shouldShowXTimeUnit =
    xColumnExists && selectedXDataType === "temporal" && !isXCountField;

  return (
    <>
      <Title text="X-Axis" />
      <div className="flex flex-row gap-2 justify-between">
        <ColumnSelector
          form={form}
          name="general.xColumn.field"
          columns={fields}
        />
        {shouldShowXAggregation && (
          <AggregationSelect form={form} name="general.xColumn.aggregate" />
        )}
      </div>
      {xColumnExists && !isXCountField && (
        <DataTypeSelect
          form={form}
          formFieldLabel="Data Type"
          name="general.xColumn.selectedDataType"
          defaultValue={inferredXDataType}
        />
      )}
      {shouldShowXTimeUnit && (
        <TimeUnitSelect
          form={form}
          name="general.xColumn.timeUnit"
          formFieldLabel="Time Resolution"
        />
      )}
      {xColumnExists && !isXCountField && (
        <SelectField
          form={form}
          name="general.xColumn.sort"
          formFieldLabel="Sort"
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
          defaultValue={formValues.general?.xColumn?.sort ?? "ascending"}
        />
      )}
    </>
  );
};

export const YAxis: React.FC<{
  form: UseFormReturn<z.infer<typeof ChartSchema>>;
  fields: Field[];
}> = ({ form, fields }) => {
  const formValues = useWatch({ control: form.control });
  const yColumn = formValues.general?.yColumn;
  const yColumnExists = FieldValidators.exists(yColumn?.field);

  const inferredYDataType = yColumn?.type
    ? TypeConverters.toSelectableDataType(yColumn.type)
    : "string";

  const selectedYDataType = yColumn?.selectedDataType || inferredYDataType;
  const isYCountField = yColumn?.field === COUNT_FIELD;

  const shouldShowYAggregation =
    yColumnExists && selectedYDataType !== "temporal" && !isYCountField;

  const shouldShowYTimeUnit =
    yColumnExists && selectedYDataType === "temporal" && !isYCountField;

  return (
    <>
      <Title text="Y-Axis" />
      <div className="flex flex-row gap-2 justify-between">
        <ColumnSelector
          form={form}
          name="general.yColumn.field"
          columns={fields}
        />
        {shouldShowYAggregation && (
          <AggregationSelect form={form} name="general.yColumn.aggregate" />
        )}
      </div>

      {yColumnExists && !isYCountField && (
        <DataTypeSelect
          form={form}
          formFieldLabel="Data Type"
          name="general.yColumn.selectedDataType"
          defaultValue={inferredYDataType}
        />
      )}
      {shouldShowYTimeUnit && (
        <TimeUnitSelect
          form={form}
          name="general.yColumn.timeUnit"
          formFieldLabel="Time Resolution"
        />
      )}
    </>
  );
};

export const ColorByAxis: React.FC<{
  form: UseFormReturn<z.infer<typeof ChartSchema>>;
  fields: Field[];
}> = ({ form, fields }) => {
  return (
    <>
      <BooleanField
        form={form}
        name="general.horizontal"
        formFieldLabel="Horizontal chart"
      />
      <Title text="Color by" />
      <div className="flex flex-row justify-between">
        <ColumnSelector
          form={form}
          name="general.colorByColumn.field"
          columns={fields}
        />
        <AggregationSelect form={form} name="general.colorByColumn.aggregate" />
      </div>
    </>
  );
};
