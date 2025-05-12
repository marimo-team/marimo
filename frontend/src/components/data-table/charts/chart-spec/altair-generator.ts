/* Copyright 2024 Marimo. All rights reserved. */
import {
  FunctionCall,
  Literal,
  type PythonCode,
  Variable,
  VariableDeclaration,
} from "@/utils/python-poet/poet";
import type { ChartSchemaType } from "../schemas";
import type { ChartType } from "../types";
import { convertChartTypeToMark } from "./types";

export function generateAltairChart(
  chartType: ChartType,
  spec: ChartSchemaType,
  datasource: string,
): PythonCode {
  let code = new FunctionCall("alt.Chart", [new Variable(datasource)], true);

  code = code.chain(`mark_${convertChartTypeToMark(chartType)}`, []);

  if (chartType === "bar") {
    code = code.chain("encode", {
      x: new FunctionCall("alt.X", [new Literal(spec.general.xColumn?.field)]),
      y: new FunctionCall("alt.Y", [new Literal(spec.general.yColumn?.field)]),
    });
  }

  return code;
}

export function generateAltairChartSnippet(
  chartType: ChartType,
  spec: ChartSchemaType,
  datasource: string,
): string {
  const code = generateAltairChart(chartType, spec, datasource).toCode();
  return `
${new VariableDeclaration("_chart", code).toCode()}
_chart
  `.trim();
}
