/* Copyright 2024 Marimo. All rights reserved. */

import { useWatch } from "react-hook-form";
import type { ChartType } from "../types";
import { FieldValidators } from "../spec";
import type { UseFormReturn } from "react-hook-form";
import type { ChartSchema } from "../schemas";
import type { Field } from "./form-components";
import type { z } from "zod";
import { NumberField } from "./form-components";
import { ColorByAxis, XAxis, YAxis } from "./chart-components";

export const HeatmapForm: React.FC<{
  form: UseFormReturn<z.infer<typeof ChartSchema>>;
  fields: Field[];
  saveForm: () => void;
  chartType: ChartType;
}> = ({ form, fields, saveForm, chartType }) => {
  const formValues = useWatch({ control: form.control });
  const xColumnExists = FieldValidators.exists(
    formValues.general?.xColumn?.field,
  );
  const yColumnExists = FieldValidators.exists(
    formValues.general?.yColumn?.field,
  );

  return (
    <>
      <XAxis form={form} fields={fields} />
      {xColumnExists && (
        <NumberField
          form={form}
          name="xAxis.bin.maxbins"
          formFieldLabel="Number of boxes (max)"
          className="justify-between"
        />
      )}
      <YAxis form={form} fields={fields} />
      {yColumnExists && (
        <NumberField
          form={form}
          name="yAxis.bin.maxbins"
          formFieldLabel="Number of boxes (max)"
          className="justify-between"
        />
      )}
      <ColorByAxis form={form} fields={fields} />
    </>
  );
};
