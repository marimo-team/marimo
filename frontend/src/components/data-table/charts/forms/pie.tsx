/* Copyright 2024 Marimo. All rights reserved. */

import { ColumnSelector } from "./form-fields";
import { Title } from "../common/layouts";
import { useWatch } from "react-hook-form";
import { FieldValidators } from "../spec";
import type { UseFormReturn } from "react-hook-form";
import { TypeConverters } from "../spec";
import type { ChartSchema } from "../schemas";
import type { z } from "zod";
import {
  DataTypeSelect,
  AggregationSelect,
  TooltipSelect,
  NumberField,
} from "./form-fields";
import { useChartFormContext } from "../context";

export const PieForm: React.FC<{
  form: UseFormReturn<z.infer<typeof ChartSchema>>;
  saveForm: () => void;
}> = ({ form, saveForm }) => {
  const context = useChartFormContext();
  const formValues = useWatch({ control: form.control });
  const colorByColumn = formValues.general?.colorByColumn;

  const fields = context.fields;

  const inferredColorByDataType = colorByColumn?.type
    ? TypeConverters.toSelectableDataType(colorByColumn.type)
    : "string";

  return (
    <>
      <Title text="Color by" />
      <ColumnSelector
        fieldName="general.colorByColumn.field"
        columns={fields}
        includeCountField={false}
      />
      {FieldValidators.exists(colorByColumn?.field) && (
        <DataTypeSelect
          fieldName="general.colorByColumn.selectedDataType"
          label="Data Type"
          defaultValue={inferredColorByDataType}
        />
      )}

      <Title text="Size by" />
      <div className="flex flex-row justify-between">
        <ColumnSelector fieldName="general.yColumn.field" columns={fields} />
        <AggregationSelect fieldName="general.yColumn.aggregate" />
      </div>

      <hr className="my-1" />
      <Title text="General" />
      <TooltipSelect
        fieldName="general.tooltips"
        fields={fields}
        saveFunction={saveForm}
        label="Tooltips"
      />
      <NumberField
        fieldName="style.innerRadius"
        label="Donut size"
        className="w-32"
      />
    </>
  );
};
