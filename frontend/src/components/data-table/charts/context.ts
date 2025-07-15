/* Copyright 2024 Marimo. All rights reserved. */

import { createContext, use } from "react";
import { Functions } from "@/utils/functions";
import type { Field } from "./components/form-fields";
import { ChartType } from "./types";

export const ChartFormContext = createContext<{
  fields: Field[];
  saveForm: () => void;
  chartType: ChartType;
}>({
  fields: [],
  saveForm: Functions.NOOP,
  chartType: ChartType.LINE,
});

export const useChartFormContext = () => {
  return use(ChartFormContext);
};
