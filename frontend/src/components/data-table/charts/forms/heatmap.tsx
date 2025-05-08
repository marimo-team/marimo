/* Copyright 2024 Marimo. All rights reserved. */

import { useWatch } from "react-hook-form";
import { FieldValidators } from "../spec";
import type { UseFormReturn } from "react-hook-form";
import type { ChartSchema } from "../schemas";
import type { z } from "zod";
import { NumberField } from "./form-fields";
import { ColorByAxis, XAxis, YAxis } from "./chart-components";

export const HeatmapForm: React.FC<{
  form: UseFormReturn<z.infer<typeof ChartSchema>>;
  saveForm: () => void;
}> = ({ form }) => {
  const formValues = useWatch({ control: form.control });
  const xColumnExists = FieldValidators.exists(
    formValues.general?.xColumn?.field,
  );
  const yColumnExists = FieldValidators.exists(
    formValues.general?.yColumn?.field,
  );

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
        <NumberField
          fieldName="yAxis.bin.maxbins"
          label="Number of boxes (max)"
          className="justify-between"
        />
      )}
      <ColorByAxis />
    </>
  );
};
