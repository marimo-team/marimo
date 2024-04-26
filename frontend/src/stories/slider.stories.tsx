/* Copyright 2024 Marimo. All rights reserved. */
import { Slider } from "@/components/ui/slider";
import { Functions } from "@/utils/functions";

export default {
  title: "Slider",
  component: Slider,
};

export const WithValue = {
  render: () => (
    <Slider valueMap={Functions.identity} value={[10]} max={100} step={1} />
  ),
  name: "With Value",
};

export const WithDefaultValue = {
  render: () => (
    <Slider
      valueMap={Functions.identity}
      defaultValue={[33]}
      max={100}
      step={1}
    />
  ),
  name: "With Default Value",
};
