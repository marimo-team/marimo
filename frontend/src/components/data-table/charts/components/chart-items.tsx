/* Copyright 2024 Marimo. All rights reserved. */

import { ChevronDown, Loader2 } from "lucide-react";
import { capitalize } from "lodash-es";
import * as SelectPrimitive from "@radix-ui/react-select";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectValue,
} from "@/components/ui/select";
import { CHART_TYPE_ICON, COUNT_FIELD, EMPTY_VALUE } from "../constants";
import { ErrorBanner } from "@/plugins/impl/common/error-banner";
import { buttonVariants } from "@/components/ui/button";
import { useFormContext, useWatch } from "react-hook-form";
import type { z } from "zod";
import type { ChartSchema } from "../schemas";
import { isFieldSet } from "../chart-spec/spec";
import {
  ColumnSelector,
  AggregationSelect,
  DataTypeSelect,
  TimeUnitSelect,
  BooleanField,
  SortField,
  NumberField,
  BinFields,
} from "./form-fields";
import { CHART_TYPES, type ChartType } from "../types";
import React from "react";
import { FieldSection, Title } from "./layouts";
import { useChartFormContext } from "../context";
import { convertDataTypeToSelectable } from "../chart-spec/types";

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

export const XAxis: React.FC = () => {
  const form = useFormContext<z.infer<typeof ChartSchema>>();
  const formValues = useWatch({ control: form.control });
  const context = useChartFormContext();

  const xColumn = formValues.general?.xColumn;
  const xColumnExists = isFieldSet(xColumn?.field);

  const inferredXDataType = xColumn?.type
    ? convertDataTypeToSelectable(xColumn.type)
    : "string";

  const selectedXDataType = xColumn?.selectedDataType || inferredXDataType;
  const isXCountField = xColumn?.field === COUNT_FIELD;

  const shouldShowXAggregation =
    xColumnExists && selectedXDataType !== "temporal" && !isXCountField;

  const shouldShowXTimeUnit =
    xColumnExists && selectedXDataType === "temporal" && !isXCountField;

  // const showBinFields = xColumn?.selectedDataType === "number";

  return (
    <FieldSection>
      <Title text="X-Axis" />
      <div className="flex flex-row justify-between">
        <ColumnSelector
          fieldName="general.xColumn.field"
          columns={context.fields}
        />
        {shouldShowXAggregation && (
          <AggregationSelect
            fieldName="general.xColumn.aggregate"
            selectedDataType={selectedXDataType}
            binFieldName="xAxis.bin.binned"
          />
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
        <>
          <SortField
            fieldName="general.xColumn.sort"
            label="Sort"
            defaultValue={formValues.general?.xColumn?.sort}
          />
          {/* {showBinFields && <BinFields fieldName="xAxis" />} */}
          <BinFields fieldName="xAxis" />
        </>
      )}
    </FieldSection>
  );
};

export const YAxis: React.FC = () => {
  const form = useFormContext<z.infer<typeof ChartSchema>>();
  const formValues = useWatch({ control: form.control });
  const context = useChartFormContext();

  const yColumn = formValues.general?.yColumn;
  const yColumnExists = isFieldSet(yColumn?.field);
  const xColumn = formValues.general?.xColumn;
  const xColumnExists = isFieldSet(xColumn?.field);

  const inferredYDataType = yColumn?.type
    ? convertDataTypeToSelectable(yColumn.type)
    : "string";

  const selectedYDataType = yColumn?.selectedDataType || inferredYDataType;
  const isYCountField = yColumn?.field === COUNT_FIELD;

  const shouldShowYAggregation =
    yColumnExists && selectedYDataType !== "temporal" && !isYCountField;

  const shouldShowYTimeUnit =
    yColumnExists && selectedYDataType === "temporal" && !isYCountField;

  // const showBinFields =
  //   yColumnExists && !isYCountField && yColumn.selectedDataType === "number";

  return (
    <FieldSection>
      <Title text="Y-Axis" />
      <div className="flex flex-row justify-between">
        <ColumnSelector
          fieldName="general.yColumn.field"
          columns={context.fields}
        />
        {shouldShowYAggregation && (
          <AggregationSelect
            fieldName="general.yColumn.aggregate"
            selectedDataType={selectedYDataType}
            binFieldName="yAxis.bin.binned"
          />
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
      {/* {showBinFields && <BinFields fieldName="yAxis" />} */}
      {yColumnExists && xColumnExists && (
        <BooleanField fieldName="general.horizontal" label="Invert axis" />
      )}
    </FieldSection>
  );
};

export const ColorByAxis: React.FC = () => {
  const { fields } = useChartFormContext();
  const form = useFormContext<z.infer<typeof ChartSchema>>();
  const formValues = useWatch({ control: form.control });

  let selectedColorByDataType =
    formValues.general?.colorByColumn?.selectedDataType;
  if (selectedColorByDataType === EMPTY_VALUE || !selectedColorByDataType) {
    selectedColorByDataType = "string";
  }

  // const showBinFields =
  //   formValues.general?.colorByColumn?.type &&
  //   ["number", "integer"].includes(formValues.general?.colorByColumn?.type) &&
  //   formValues.general?.colorByColumn?.field !== COUNT_FIELD;

  return (
    <FieldSection>
      <Title text="Color by" />
      <div className="flex flex-row justify-between">
        <ColumnSelector
          fieldName="general.colorByColumn.field"
          columns={fields}
        />
        <AggregationSelect
          fieldName="general.colorByColumn.aggregate"
          selectedDataType={selectedColorByDataType}
          binFieldName="color.bin.binned"
        />
      </div>
      {/* {showBinFields && <BinFields fieldName="color" />} */}
    </FieldSection>
  );
};

export const Facet: React.FC = () => {
  const context = useChartFormContext();
  const fields = context.fields;

  const form = useFormContext<z.infer<typeof ChartSchema>>();
  const formValues = useWatch({ control: form.control });

  const renderField = (facet: "column" | "row") => {
    const field = formValues.general?.facet?.[facet];
    const fieldExists = isFieldSet(field?.field);

    const inferredDataType = field?.type
      ? convertDataTypeToSelectable(field.type)
      : "string";
    const selectedDataType = field?.selectedDataType || inferredDataType;

    const shouldShowTimeUnit = fieldExists && selectedDataType === "temporal";
    const canShowBin = fieldExists && selectedDataType === "number";

    const linkFieldName =
      facet === "row"
        ? ("general.facet.row.linkYAxis" as const)
        : ("general.facet.column.linkXAxis" as const);

    return (
      <div className="flex flex-col gap-1">
        <div className="flex flex-row justify-between">
          <p className="font-semibold">{capitalize(facet)}</p>
          <ColumnSelector
            fieldName={`general.facet.${facet}.field`}
            columns={fields}
          />
        </div>
        {fieldExists && (
          <>
            <DataTypeSelect
              label="Data Type"
              fieldName={`general.facet.${facet}.selectedDataType`}
              defaultValue={inferredDataType}
            />
            {shouldShowTimeUnit && (
              <TimeUnitSelect
                fieldName={`general.facet.${facet}.timeUnit`}
                label="Time Resolution"
              />
            )}
            {canShowBin && (
              <div className="flex flex-row justify-between">
                <BooleanField
                  fieldName={`general.facet.${facet}.binned`}
                  label="Binned"
                />
                <NumberField
                  fieldName={`general.facet.${facet}.maxbins`}
                  label="Max Bins"
                  placeholder="10"
                />
              </div>
            )}
            <SortField fieldName={`general.facet.${facet}.sort`} label="Sort" />
            <BooleanField
              fieldName={linkFieldName}
              label={`Link ${facet === "row" ? "Y" : "X"} Axes`}
            />
          </>
        )}
      </div>
    );
  };

  return (
    <FieldSection className="gap-3">
      {renderField("row")}
      {renderField("column")}
    </FieldSection>
  );
};
