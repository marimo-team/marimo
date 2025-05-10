/* Copyright 2024 Marimo. All rights reserved. */

import { createContext, useContext } from "react";
import type { Field } from "./components/form-fields";

export const ChartFormContext = createContext<{
  fields: Field[];
}>({
  fields: [],
});

export const useChartFormContext = () => {
  return useContext(ChartFormContext);
};
