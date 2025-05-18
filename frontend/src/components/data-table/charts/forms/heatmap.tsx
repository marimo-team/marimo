/* Copyright 2024 Marimo. All rights reserved. */

import { useFormContext, useWatch } from "react-hook-form";
import { isFieldSet } from "../chart-spec/spec";
import type { ChartSchema } from "../schemas";
import type { z } from "zod";
import { NumberField } from "../components/form-fields";
import { ColorByAxis, XAxis, YAxis } from "../components/chart-items";
import { OtherOptions } from "./common-chart";
import { FormSectionHorizontalRule } from "../components/layouts";

export const HeatmapForm: React.FC = () => {
  const form = useFormContext<z.infer<typeof ChartSchema>>();

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
