/* Copyright 2024 Marimo. All rights reserved. */
import { Slider } from "@/components/ui/slider";

export default {
  title: "Slider",
  component: Slider,
};

export const WithValue = {
  render: () => <Slider value={[10]} max={100} step={1} />,
  name: "With Value",
};

export const WithDefaultValue = {
  render: () => <Slider defaultValue={[33]} max={100} step={1} />,
  name: "With Default Value",
};
