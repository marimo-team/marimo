/* Copyright 2024 Marimo. All rights reserved. */

import { ColumnSelector } from "./form-components";
import { Title } from "./chart-components";
import { useWatch } from "react-hook-form";
import type { ChartType } from "../types";
import { FieldValidators } from "../spec";
import type { UseFormReturn } from "react-hook-form";
import { TypeConverters } from "../spec";
import type { ChartSchema } from "../schemas";
import type { Field } from "./form-components";
import type { z } from "zod";
import {
  DataTypeSelect,
  AggregationSelect,
  TooltipSelect,
  NumberField,
} from "./form-components";

export const PieForm: React.FC<{
  form: UseFormReturn<z.infer<typeof ChartSchema>>;
  fields: Field[];
  saveForm: () => void;
  chartType: ChartType;
}> = ({ form, fields, saveForm, chartType }) => {
  const formValues = useWatch({ control: form.control });
  const colorByColumn = formValues.general?.colorByColumn;

  const inferredColorByDataType = colorByColumn?.type
    ? TypeConverters.toSelectableDataType(colorByColumn.type)
    : "string";

  return (
    <>
      <Title text="Color by" />
      <ColumnSelector
        form={form}
        name="general.colorByColumn.field"
        columns={fields}
        includeCountField={false}
      />
      {FieldValidators.exists(colorByColumn?.field) && (
        <DataTypeSelect
          form={form}
          name="general.colorByColumn.selectedDataType"
          formFieldLabel="Data Type"
          defaultValue={inferredColorByDataType}
        />
      )}

      <Title text="Size by" />
      <div className="flex flex-row justify-between">
        <ColumnSelector
          form={form}
          name="general.yColumn.field"
          columns={fields}
        />
        <AggregationSelect form={form} name="general.yColumn.aggregate" />
      </div>

      <hr />
      <Title text="General" />
      <TooltipSelect
        form={form}
        name="general.tooltips"
        fields={fields}
        saveFunction={saveForm}
        formFieldLabel="Tooltips"
      />
      <NumberField
        form={form}
        name="style.innerRadius"
        formFieldLabel="Donut size"
        className="w-32"
      />
    </>
  );
};
