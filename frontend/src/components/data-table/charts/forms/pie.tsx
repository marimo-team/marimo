/* Copyright 2024 Marimo. All rights reserved. */

import { ColumnSelector } from "../components/form-fields";
import { FormSectionHorizontalRule, Title } from "../components/layouts";
import { useFormContext, useWatch } from "react-hook-form";
import { isFieldSet } from "../chart-spec/spec";
import {
  DataTypeSelect,
  AggregationSelect,
  NumberField,
} from "../components/form-fields";
import { useChartFormContext } from "../context";
import { OtherOptions } from "./common-chart";
import { convertDataTypeToSelectable } from "../chart-spec/types";
import { EMPTY_VALUE } from "../constants";
import type { ChartSchemaType } from "../schemas";

export const PieForm: React.FC = () => {
  const form = useFormContext<ChartSchemaType>();
  const { fields } = useChartFormContext();

  const formValues = useWatch({ control: form.control });
  const colorByColumn = formValues.general?.colorByColumn;

  let ySelectedDataType = formValues.general?.yColumn?.selectedDataType;
  if (ySelectedDataType === EMPTY_VALUE || !ySelectedDataType) {
    ySelectedDataType = "string";
  }

  const inferredColorByDataType = colorByColumn?.type
    ? convertDataTypeToSelectable(colorByColumn.type)
    : "string";

  return (
    <>
      <Title text="Color by" />
      <ColumnSelector
        fieldName="general.colorByColumn.field"
        columns={fields}
        includeCountField={false}
      />
      {isFieldSet(colorByColumn?.field) && (
        <DataTypeSelect
          fieldName="general.colorByColumn.selectedDataType"
          label="Data Type"
          defaultValue={inferredColorByDataType}
        />
      )}

      <Title text="Size by" />
      <div className="flex flex-row justify-between">
        <ColumnSelector fieldName="general.yColumn.field" columns={fields} />
        <AggregationSelect
          fieldName="general.yColumn.aggregate"
          selectedDataType={ySelectedDataType}
          binFieldName="yAxis.bin.binned"
        />
      </div>

      <NumberField
        fieldName="style.innerRadius"
        label="Donut size"
        className="w-32"
      />

      <FormSectionHorizontalRule />
      <OtherOptions />
    </>
  );
};
