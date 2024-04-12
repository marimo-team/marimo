/* Copyright 2024 Marimo. All rights reserved. */
import { NumberField } from "@/components/ui/number-field";
import { Label } from "@/components/ui/label";

export default {
  title: "NumberField",
  component: NumberField,
};

export const Default = {
  render: () => <NumberField placeholder="..." />,
  name: "Default",
};

export const Disabled = {
  render: () => <NumberField placeholder="..." isDisabled={true} />,
  name: "Disabled",
};

export const WithLabel = {
  render: () => (
    <div className="grid w-full gap-1.5">
      <Label htmlFor="message">Your message</Label>
      <NumberField placeholder="..." id="message" />
    </div>
  ),

  name: "With Label",
};

export const MinAndMax = {
  render: () => (
    <div className="grid w-full gap-1.5">
      <NumberField placeholder="..." minValue={-10} maxValue={100} />
      <NumberField placeholder="..." minValue={10} maxValue={100} />
    </div>
  ),

  name: "Min and Max",
};
