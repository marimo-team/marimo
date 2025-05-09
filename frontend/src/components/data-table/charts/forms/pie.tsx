/* Copyright 2024 Marimo. All rights reserved. */

import { ColumnSelector } from "../components/form-fields";
import { FormSectionHorizontalRule, Title } from "../components/layouts";
import { useFormContext, useWatch } from "react-hook-form";
import { FieldValidators } from "../spec";
import { TypeConverters } from "../spec";
import type { ChartSchema } from "../schemas";
import type { z } from "zod";
import {
  DataTypeSelect,
  AggregationSelect,
  NumberField,
} from "../components/form-fields";
import { useChartFormContext } from "../context";
import { OtherOptions } from "./common-chart";

export const PieForm: React.FC<{
  saveForm: () => void;
}> = ({ saveForm }) => {
  const form = useFormContext<z.infer<typeof ChartSchema>>();
  const { fields } = useChartFormContext();
  const formValues = useWatch({ control: form.control });
  const colorByColumn = formValues.general?.colorByColumn;

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

      <NumberField
        fieldName="style.innerRadius"
        label="Donut size"
        className="w-32"
      />

      <FormSectionHorizontalRule />
      <OtherOptions saveForm={saveForm} />
    </>
  );
};
