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
import { CHART_TYPE_ICON, COUNT_FIELD, type EMPTY_VALUE } from "../constants";
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
  type FieldName,
} from "./form-fields";
import { CHART_TYPES, type ChartType, type SelectableDataType } from "../types";
import React from "react";
import { FieldSection, Title } from "./layouts";
import { useChartFormContext } from "../context";
import { convertDataTypeToSelectable } from "../chart-spec/types";
import type { DataType } from "@/core/kernel/messages";

type SelectedDataType = SelectableDataType | typeof EMPTY_VALUE;
type FieldDataType = DataType | typeof EMPTY_VALUE;

// Utility functions for field type checking
function isNonCountField(field?: {
  field?: string;
}) {
  return isFieldSet(field?.field) && field?.field !== COUNT_FIELD;
}

function isNumberField(field?: {
  field?: string;
  selectedDataType?: SelectedDataType;
}) {
  return field?.selectedDataType === "number" && isNonCountField(field);
}

function isTemporalField(field?: {
  field?: string;
  selectedDataType?: SelectedDataType;
}) {
  return field?.selectedDataType === "temporal" && isNonCountField(field);
}

function isNonTemporalField(field?: {
  field?: string;
  selectedDataType?: SelectedDataType;
}) {
  return field?.selectedDataType !== "temporal" && isNonCountField(field);
}

// Helper to determine inferred and selected data types
function getColumnDataTypes(column?: {
  type?: FieldDataType;
  selectedDataType?: SelectedDataType;
}) {
  const inferredDataType = column?.type
    ? convertDataTypeToSelectable(column.type)
    : "string";

  return {
    inferredDataType,
    selectedDataType: column?.selectedDataType || inferredDataType,
  };
}

const ColumnSelectorWithAggregation: React.FC<{
  columnFieldName: FieldName;
  column?: {
    field?: string;
    type?: FieldDataType;
    selectedDataType?: SelectedDataType;
  };
  columns: Array<{ name: string; type: DataType }>;
  binFieldName: FieldName;
}> = ({ columnFieldName, column, columns, binFieldName }) => {
  const { selectedDataType } = getColumnDataTypes(column);

  return (
    <div className="flex flex-row justify-between">
      <ColumnSelector fieldName={columnFieldName} columns={columns} />
      {isNonTemporalField(column) && (
        <AggregationSelect
          fieldName={
            columnFieldName.replace(".field", ".aggregate") as FieldName
          }
          selectedDataType={selectedDataType}
          binFieldName={binFieldName}
        />
      )}
    </div>
  );
};

export const ChartLoadingState: React.FC = () => (
  <div className="flex items-center gap-2 justify-center">
    <Loader2 className="w-10 h-10 animate-spin" strokeWidth={1} />
    <span>Loading chart...</span>
  </div>
);

export const ChartErrorState: React.FC<{ error: Error }> = ({ error }) => (
  <div className="flex items-center justify-center">
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
  const { inferredDataType } = getColumnDataTypes(xColumn);

  return (
    <FieldSection>
      <Title text="X-Axis" />
      <ColumnSelectorWithAggregation
        columnFieldName="general.xColumn.field"
        column={xColumn}
        columns={context.fields}
        binFieldName="xAxis.bin.binned"
      />
      {isNonCountField(xColumn) && (
        <DataTypeSelect
          label="Data Type"
          fieldName="general.xColumn.selectedDataType"
          defaultValue={inferredDataType}
        />
      )}
      {isTemporalField(xColumn) && (
        <TimeUnitSelect
          fieldName="general.xColumn.timeUnit"
          label="Time Resolution"
        />
      )}
      {isNonCountField(xColumn) && (
        <>
          <SortField
            fieldName="general.xColumn.sort"
            label="Sort"
            defaultValue={formValues.general?.xColumn?.sort}
          />
          {isNumberField(xColumn) && <BinFields fieldName="xAxis" />}
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
  const { inferredDataType } = getColumnDataTypes(yColumn);

  return (
    <FieldSection>
      <Title text="Y-Axis" />
      <ColumnSelectorWithAggregation
        columnFieldName="general.yColumn.field"
        column={yColumn}
        columns={context.fields}
        binFieldName="yAxis.bin.binned"
      />

      {isNonCountField(yColumn) && (
        <DataTypeSelect
          label="Data Type"
          fieldName="general.yColumn.selectedDataType"
          defaultValue={inferredDataType}
        />
      )}
      {isTemporalField(yColumn) && (
        <TimeUnitSelect
          fieldName="general.yColumn.timeUnit"
          label="Time Resolution"
        />
      )}
      {yColumnExists && xColumnExists && (
        <BooleanField fieldName="general.horizontal" label="Invert axis" />
      )}
      {isNumberField(yColumn) && <BinFields fieldName="yAxis" />}
    </FieldSection>
  );
};

export const ColorByAxis: React.FC = () => {
  const { fields } = useChartFormContext();
  const form = useFormContext<z.infer<typeof ChartSchema>>();
  const formValues = useWatch({ control: form.control });
  const colorByColumn = formValues.general?.colorByColumn;

  const showBinFields = isNumberField(colorByColumn);

  return (
    <FieldSection>
      <Title text="Color by" />
      <ColumnSelectorWithAggregation
        columnFieldName="general.colorByColumn.field"
        column={colorByColumn}
        columns={fields}
        binFieldName="color.bin.binned"
      />
      {showBinFields && <BinFields fieldName="color" />}
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
    const { inferredDataType } = getColumnDataTypes(field);

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
            {isTemporalField(field) && (
              <TimeUnitSelect
                fieldName={`general.facet.${facet}.timeUnit`}
                label="Time Resolution"
              />
            )}
            {isNumberField(field) && (
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
              defaultValue={true}
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
