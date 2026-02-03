/* Copyright 2026 Marimo. All rights reserved. */

import { useId } from "react";
import { Label } from "@/components/ui/label";
import { NumberField } from "@/components/ui/number-field";

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
  render: function Render() {
    const id = useId();
    return (
      <div className="grid w-full gap-1.5">
        <Label htmlFor={id}>Your message</Label>
        <NumberField placeholder="..." id={id} />
      </div>
    );
  },

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
