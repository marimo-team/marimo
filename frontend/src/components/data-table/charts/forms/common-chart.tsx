/* Copyright 2024 Marimo. All rights reserved. */

import { XAxis, YAxis, ColorByAxis, Facet } from "../components/chart-items";
import { useFormContext, useWatch } from "react-hook-form";
import { isFieldSet } from "../chart-spec/spec";
import {
  BooleanField,
  InputField,
  SliderField,
  SelectField,
  ColorArrayField,
  TooltipSelect,
} from "../components/form-fields";
import { Accordion } from "@/components/ui/accordion";
import { COLOR_SCHEMES, DEFAULT_COLOR_SCHEME } from "../constants";
import { capitalize } from "lodash-es";
import { InfoIcon } from "lucide-react";
import {
  AccordionFormItem,
  AccordionFormTrigger,
  AccordionFormContent,
  Title,
  FormSectionHorizontalRule,
} from "../components/layouts";
import { useChartFormContext } from "../context";
import type { ChartSchemaType } from "../schemas";

export const CommonChartForm: React.FC = () => {
  const form = useFormContext<ChartSchemaType>();

  const formValues = useWatch({ control: form.control });
  const yColumn = formValues.general?.yColumn;
  const groupByColumn = formValues.general?.colorByColumn;

  const yColumnExists = isFieldSet(yColumn?.field);
  const showStacking = isFieldSet(groupByColumn?.field);

  return (
    <>
      <XAxis />
      <YAxis />

      {yColumnExists && (
        <>
          <ColorByAxis />
          {showStacking && (
            <div className="flex flex-row gap-2">
              <BooleanField fieldName="general.stacking" label="Stacked" />
            </div>
          )}
        </>
      )}

      <FormSectionHorizontalRule />
      <OtherOptions />
    </>
  );
};

export const StyleForm: React.FC = () => {
  return (
    <Accordion type="multiple">
      <AccordionFormItem value="general">
        <AccordionFormTrigger className="pt-0">
          <Title text="General" />
        </AccordionFormTrigger>
        <AccordionFormContent>
          <InputField label="Plot title" fieldName="general.title" />
        </AccordionFormContent>
      </AccordionFormItem>

      <AccordionFormItem value="xAxis">
        <AccordionFormTrigger>
          <Title text="X-Axis" />
        </AccordionFormTrigger>
        <AccordionFormContent>
          <InputField label="Label" fieldName="xAxis.label" />
          <SliderField
            fieldName="xAxis.width"
            label="Width"
            value={400}
            start={200}
            stop={800}
          />
        </AccordionFormContent>
      </AccordionFormItem>

      <AccordionFormItem value="yAxis">
        <AccordionFormTrigger>
          <Title text="Y-Axis" />
        </AccordionFormTrigger>
        <AccordionFormContent>
          <InputField label="Label" fieldName="yAxis.label" />
          <SliderField
            fieldName="yAxis.height"
            label="Height"
            value={300}
            start={150}
            stop={600}
          />
        </AccordionFormContent>
      </AccordionFormItem>

      <AccordionFormItem value="color">
        <AccordionFormTrigger>
          <Title text="Color" />
        </AccordionFormTrigger>
        <AccordionFormContent>
          <SelectField
            fieldName="color.scheme"
            label="Color scheme"
            defaultValue={DEFAULT_COLOR_SCHEME}
            options={COLOR_SCHEMES.map((scheme) => ({
              display: capitalize(scheme),
              value: scheme,
            }))}
          />
          <ColorArrayField fieldName="color.range" label="Color range" />
          <p className="text-xs">
            <InfoIcon className="w-2.5 h-2.5 inline mb-1 mr-1" />
            If you are using color range, color scheme will be ignored.
          </p>
        </AccordionFormContent>
      </AccordionFormItem>
    </Accordion>
  );
};

export const OtherOptions: React.FC = () => {
  const { saveForm } = useChartFormContext();

  const form = useFormContext<ChartSchemaType>();
  const formValues = useWatch({ control: form.control });
  const autoTooltips = formValues.tooltips?.auto;

  return (
    <Accordion type="multiple">
      <AccordionFormItem value="facet">
        <AccordionFormTrigger className="pt-0">
          <Title text="Faceting" />
        </AccordionFormTrigger>
        <AccordionFormContent>
          <Facet />
        </AccordionFormContent>
      </AccordionFormItem>

      <AccordionFormItem value="tooltips">
        <AccordionFormTrigger>
          <Title text="Tooltips" />
        </AccordionFormTrigger>
        <AccordionFormContent wrapperClassName="flex-row justify-between">
          <BooleanField fieldName="tooltips.auto" label="Auto" />
          {!autoTooltips && (
            <TooltipSelect
              fieldName="tooltips.fields"
              saveFunction={saveForm}
            />
          )}
        </AccordionFormContent>
      </AccordionFormItem>
    </Accordion>
  );
};
