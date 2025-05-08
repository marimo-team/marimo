/* Copyright 2024 Marimo. All rights reserved. */

import { Title, XAxis, YAxis, ColorByAxis } from "./chart-components";
import { useWatch } from "react-hook-form";
import type { ChartType } from "../types";
import { FieldValidators } from "../chart-spec";
import type { UseFormReturn } from "react-hook-form";
import type { ChartSchema } from "../chart-schemas";
import type { Field } from "./form-components";
import type { z } from "zod";
import {
  TooltipSelect,
  NumberField,
  BooleanField,
  InputField,
  SliderField,
  SelectField,
  ColorArrayField,
} from "./form-components";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import { COLOR_SCHEMES, DEFAULT_COLOR_SCHEME } from "../constants";
import { capitalize } from "lodash-es";
import { InfoIcon } from "lucide-react";

export const CommonChartForm: React.FC<{
  form: UseFormReturn<z.infer<typeof ChartSchema>>;
  fields: Field[];
  saveForm: () => void;
  chartType: ChartType;
}> = ({ form, fields, saveForm, chartType }) => {
  const formValues = useWatch({ control: form.control });
  const yColumn = formValues.general?.yColumn;
  const groupByColumn = formValues.general?.colorByColumn;

  const yColumnExists = FieldValidators.exists(yColumn?.field);
  const showStacking = FieldValidators.exists(groupByColumn?.field);

  return (
    <>
      <XAxis form={form} fields={fields} />
      <YAxis form={form} fields={fields} />

      {yColumnExists && (
        <>
          <ColorByAxis form={form} fields={fields} />
          {showStacking && (
            <div className="flex flex-row gap-2">
              <BooleanField
                form={form}
                name="general.stacking"
                formFieldLabel="Stacked"
              />
            </div>
          )}
        </>
      )}

      <hr className="my-2" />
      <TooltipSelect
        form={form}
        name="general.tooltips"
        fields={fields}
        saveFunction={saveForm}
        formFieldLabel="Tooltips"
      />
    </>
  );
};

export const StyleForm: React.FC<{
  form: UseFormReturn<z.infer<typeof ChartSchema>>;
  fields: Field[];
  saveForm: () => void;
}> = ({ form }) => {
  const renderBinFields = (axis: "x" | "y") => {
    return (
      <div className="flex flex-row gap-2 w-full">
        <BooleanField
          form={form}
          name={`${axis}Axis.bin.binned`}
          formFieldLabel="Binned"
        />
        <NumberField
          form={form}
          name={`${axis}Axis.bin.step`}
          formFieldLabel="Bin step"
          step={0.05}
          className="w-32"
        />
      </div>
    );
  };

  return (
    <Accordion type="multiple">
      <AccordionItem value="general" className="border-none">
        <AccordionTrigger className="pt-0 pb-2">
          <Title text="General" />
        </AccordionTrigger>
        <AccordionContent wrapperClassName="pb-2">
          <InputField
            form={form}
            formFieldLabel="Plot title"
            name="general.title"
          />
        </AccordionContent>
      </AccordionItem>

      <AccordionItem value="xAxis" className="border-none">
        <AccordionTrigger className="py-2">
          <Title text="X-Axis" />
        </AccordionTrigger>
        <AccordionContent wrapperClassName="pb-2 flex flex-col gap-2">
          <InputField form={form} formFieldLabel="Label" name="xAxis.label" />
          <SliderField
            form={form}
            name="xAxis.width"
            formFieldLabel="Width"
            value={400}
            start={200}
            stop={800}
          />
          {renderBinFields("x")}
        </AccordionContent>
      </AccordionItem>

      <AccordionItem value="yAxis" className="border-none">
        <AccordionTrigger className="py-2">
          <Title text="Y-Axis" />
        </AccordionTrigger>
        <AccordionContent wrapperClassName="pb-2 flex flex-col gap-2">
          <InputField form={form} formFieldLabel="Label" name="yAxis.label" />
          <SliderField
            form={form}
            name="yAxis.height"
            formFieldLabel="Height"
            value={300}
            start={150}
            stop={600}
          />
          {renderBinFields("y")}
        </AccordionContent>
      </AccordionItem>

      <AccordionItem value="color" className="border-none">
        <AccordionTrigger className="py-2">
          <Title text="Color" />
        </AccordionTrigger>
        <AccordionContent wrapperClassName="pb-2 flex flex-col gap-2">
          <SelectField
            form={form}
            name="color.scheme"
            formFieldLabel="Color scheme"
            defaultValue={DEFAULT_COLOR_SCHEME}
            options={COLOR_SCHEMES.map((scheme) => ({
              display: capitalize(scheme),
              value: scheme,
            }))}
          />
          <ColorArrayField
            form={form}
            name="color.range"
            formFieldLabel="Color range"
          />
          <p className="text-xs">
            <InfoIcon className="w-2.5 h-2.5 inline mb-1 mr-1" />
            If you are using color range, color scheme will be ignored.
          </p>
        </AccordionContent>
      </AccordionItem>
    </Accordion>
  );
};
