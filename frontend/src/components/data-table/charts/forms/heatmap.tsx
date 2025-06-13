/* Copyright 2024 Marimo. All rights reserved. */

import { useFormContext, useWatch } from "react-hook-form";
import { isFieldSet } from "../chart-spec/spec";
import { ColorByAxis, XAxis, YAxis } from "../components/chart-items";
import { NumberField } from "../components/form-fields";
import { FormSectionHorizontalRule } from "../components/layouts";
import type { ChartSchemaType } from "../schemas";
import { OtherOptions } from "./common-chart";

export const HeatmapForm: React.FC = () => {
  const form = useFormContext<ChartSchemaType>();

  const formValues = useWatch({ control: form.control });
  const xColumnExists = isFieldSet(formValues.general?.xColumn?.field);
  const yColumnExists = isFieldSet(formValues.general?.yColumn?.field);

  return (
    <>
      <XAxis />
      {xColumnExists && (
        <NumberField
          fieldName="xAxis.bin.maxbins"
          label="Number of boxes (max)"
          className="justify-between"
        />
      )}
      <YAxis />
      {yColumnExists && (
        <>
          <NumberField
            fieldName="yAxis.bin.maxbins"
            label="Number of boxes (max)"
            className="justify-between"
          />
          <ColorByAxis />
        </>
      )}

      <FormSectionHorizontalRule />
      <OtherOptions />
    </>
  );
};
