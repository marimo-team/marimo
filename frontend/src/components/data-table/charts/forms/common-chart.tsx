/* Copyright 2024 Marimo. All rights reserved. */

import { capitalize } from "lodash-es";
import { InfoIcon, TriangleAlert } from "lucide-react";
import { useFormContext, useWatch } from "react-hook-form";
import { Accordion } from "@/components/ui/accordion";
import { Tooltip } from "@/components/ui/tooltip";
import { isFieldSet } from "../chart-spec/spec";
import { ColorByAxis, Facet, XAxis, YAxis } from "../components/chart-items";
import {
  BooleanField,
  ColorArrayField,
  InputField,
  SelectField,
  SliderField,
  TooltipSelect,
} from "../components/form-fields";
import {
  AccordionFormContent,
  AccordionFormItem,
  AccordionFormTrigger,
  FormSectionHorizontalRule,
  Title,
} from "../components/layouts";
import { COLOR_SCHEMES, DEFAULT_COLOR_SCHEME } from "../constants";
import { useChartFormContext } from "../context";
import type { ChartSchemaType } from "../schemas";
import { ChartType, COLOR_BY_FIELDS, NONE_VALUE } from "../types";

export const CommonChartForm: React.FC = () => {
  const form = useFormContext<ChartSchemaType>();

  const formValues = useWatch({ control: form.control });
  const yColumn = formValues.general?.yColumn;
  const groupByColumn = formValues.general?.colorByColumn;

  const yColumnExists = isFieldSet(yColumn?.field);

  const { chartType } = useChartFormContext();

  const showStacking =
    isFieldSet(groupByColumn?.field) &&
    (chartType === ChartType.BAR || chartType === ChartType.LINE);

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
      <Tooltip
        delayDuration={100}
        content="Charts are saved in local storage but we recommend saving Python code in a new cell until this feature is stable."
      >
        <div className="flex items-center gap-1">
          <TriangleAlert className="h-3 w-3 mb-0.5 text-muted-foreground" />
          <p className="text-xs text-muted-foreground">Local storage</p>
        </div>
      </Tooltip>
    </>
  );
};

export const StyleForm: React.FC = () => {
  const { chartType } = useChartFormContext();

  return (
    <Accordion type="multiple">
      <AccordionFormItem value="general">
        <AccordionFormTrigger className="pt-0">
          <Title text="General" />
        </AccordionFormTrigger>
        <AccordionFormContent>
          <InputField label="Plot title" fieldName="general.title" />
          <BooleanField
            fieldName="style.gridLines"
            label="Show grid lines"
            defaultValue={chartType === ChartType.SCATTER}
          />
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
            fieldName="color.field"
            label="Field"
            options={COLOR_BY_FIELDS.map((field) => ({
              display: capitalize(field),
              value: field,
            }))}
            defaultValue={NONE_VALUE}
          />
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
          <Title
            text="Faceting"
            tooltip="Repeat the chart for each unique field value"
          />
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
          <BooleanField
            fieldName="tooltips.auto"
            label="Include X, Y and Color"
          />
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
