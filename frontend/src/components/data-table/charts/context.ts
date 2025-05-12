/* Copyright 2024 Marimo. All rights reserved. */

import { createContext, useContext } from "react";
import type { Field } from "./components/form-fields";
import { Functions } from "@/utils/functions";

export const ChartFormContext = createContext<{
  fields: Field[];
  saveForm: () => void;
}>({
  fields: [],
  saveForm: Functions.NOOP,
});

export const useChartFormContext = () => {
  return useContext(ChartFormContext);
};
