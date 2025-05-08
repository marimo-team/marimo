/* Copyright 2024 Marimo. All rights reserved. */

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
import { CHART_TYPE_ICON, COUNT_FIELD } from "../constants";
import { ErrorBanner } from "@/plugins/impl/common/error-banner";
import { buttonVariants } from "@/components/ui/button";
import { type UseFormReturn, useWatch } from "react-hook-form";
import type { z } from "zod";
import type { ChartSchema } from "../schemas";
import { FieldValidators, TypeConverters } from "../spec";
import {
  ColumnSelector,
  AggregationSelect,
  DataTypeSelect,
  TimeUnitSelect,
  SelectField,
  BooleanField,
  type Field,
} from "./form-fields";
import { CHART_TYPES, type ChartType, SORT_TYPES } from "../types";
import React from "react";
import { IconWithText, Title } from "../common/layouts";

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
    <div className="flex flex-col gap-1">
      <Title text="X-Axis" />
      <div className="flex flex-row gap-2 justify-between">
        <ColumnSelector fieldName="general.xColumn.field" columns={fields} />
        {shouldShowXAggregation && (
          <AggregationSelect fieldName="general.xColumn.aggregate" />
        )}
      </div>
      {xColumnExists && !isXCountField && (
        <DataTypeSelect
          label="Data Type"
          fieldName="general.xColumn.selectedDataType"
          defaultValue={inferredXDataType}
        />
      )}
      {shouldShowXTimeUnit && (
        <TimeUnitSelect
          fieldName="general.xColumn.timeUnit"
          label="Time Resolution"
        />
      )}
      {xColumnExists && !isXCountField && (
        <SelectField
          fieldName="general.xColumn.sort"
          label="Sort"
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
    </div>
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
    <div className="flex flex-col gap-1">
      <Title text="Y-Axis" />
      <div className="flex flex-row gap-2 justify-between">
        <ColumnSelector fieldName="general.yColumn.field" columns={fields} />
        {shouldShowYAggregation && (
          <AggregationSelect fieldName="general.yColumn.aggregate" />
        )}
      </div>

      {yColumnExists && !isYCountField && (
        <DataTypeSelect
          label="Data Type"
          fieldName="general.yColumn.selectedDataType"
          defaultValue={inferredYDataType}
        />
      )}
      {shouldShowYTimeUnit && (
        <TimeUnitSelect
          fieldName="general.yColumn.timeUnit"
          label="Time Resolution"
        />
      )}
    </div>
  );
};

export const ColorByAxis: React.FC<{
  form: UseFormReturn<z.infer<typeof ChartSchema>>;
  fields: Field[];
}> = ({ fields }) => {
  return (
    <div className="flex flex-col gap-1">
      <BooleanField fieldName="general.horizontal" label="Horizontal chart" />
      <Title text="Color by" />
      <div className="flex flex-row justify-between">
        <ColumnSelector
          fieldName="general.colorByColumn.field"
          columns={fields}
        />
        <AggregationSelect fieldName="general.colorByColumn.aggregate" />
      </div>
    </div>
  );
};

export const Facet: React.FC<{
  fields: Field[];
}> = ({ fields }) => {
  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex flex-row gap-2 justify-between">
        <p>Row</p>
        <ColumnSelector fieldName="general.facet.row.field" columns={fields} />
      </div>
      <div className="flex flex-row gap-2 justify-between">
        <p>Column</p>
        <ColumnSelector
          fieldName="general.facet.column.field"
          columns={fields}
        />
      </div>
    </div>
  );
};
