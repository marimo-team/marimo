/* Copyright 2024 Marimo. All rights reserved. */

import { createContext, use } from "react";
import { Functions } from "@/utils/functions";
import type { Field } from "./components/form-fields";

export const ChartFormContext = createContext<{
  fields: Field[];
  saveForm: () => void;
}>({
  fields: [],
  saveForm: Functions.NOOP,
});

export const useChartFormContext = () => {
  return use(ChartFormContext);
};
