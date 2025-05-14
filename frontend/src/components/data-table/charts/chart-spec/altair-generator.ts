/* Copyright 2024 Marimo. All rights reserved. */
import {
  FunctionArg,
  FunctionCall,
  Literal,
  objectsToPythonCode,
  type PythonCode,
  Variable,
  VariableDeclaration,
} from "@/utils/python-poet/poet";
import type { AxisSchema } from "../schemas";
import { DATA_TYPE_LETTERS } from "../types";
import type { z } from "zod";
import { getAggregate } from "./encodings";
import { COUNT_FIELD } from "../constants";
import type { VegaLiteSpec } from "@/plugins/impl/vega/types";

/**
 * Generates Python code for an Altair chart.
 */
export function generateAltairChart(
  spec: VegaLiteSpec,
  datasource: string,
): PythonCode {
  let code = new FunctionCall("alt.Chart", [new Variable(datasource)], true);

  const encodeArgs: Record<string, PythonCode> = {};

  // Check if spec has a mark property (only exists on unit specs)
  const hasMarkProperty = "mark" in spec;
  if (hasMarkProperty) {
    const markSpec = spec.mark;
    const markType =
      typeof markSpec === "string"
        ? markSpec
        : "type" in markSpec
          ? markSpec.type
          : undefined;

    if (markType) {
      code = code.chain(`mark_${markType}`, []);
    }
  }

  const hasEncodings = "encoding" in spec;
  if (hasEncodings) {
    const encodings = spec.encoding;

    if (encodings?.x) {
      encodeArgs.x = objectsToPythonCode([encodings.x], "alt.X");
    }

    if (encodings?.y) {
      encodeArgs.y = objectsToPythonCode([encodings.y], "alt.Y");
    }

    if (encodings?.color) {
      encodeArgs.color = objectsToPythonCode([encodings.color], "alt.Color");
    }

    if (encodings?.tooltip) {
      const tooltip = encodings.tooltip;
      const tooltipArray = Array.isArray(tooltip) ? tooltip : [tooltip];
      const tooltipCode = objectsToPythonCode(tooltipArray, "alt.Tooltip");
      encodeArgs.tooltip = tooltipCode;
    }
  }

  code = code.chain("encode", encodeArgs);
  return code;
}

/**
 * Wraps altair code in a variable declaration.
 *
 * @param chartType - The type of chart to generate.
 * @param spec - The specification of the chart.
 * @param datasource - The name of the datasource to use.
 * @param variableName - The name of the variable to declare.
 */
export function generateAltairChartSnippet(
  spec: VegaLiteSpec,
  datasource: string,
  variableName: string,
): string {
  const code = generateAltairChart(spec, datasource).toCode();
  return `
${new VariableDeclaration(variableName, code).toCode()}
${variableName}
  `.trim();
}

function generateAxisCode(column?: z.infer<typeof AxisSchema>): PythonCode[] {
  if (!column) {
    return [];
  }

  const result: PythonCode[] = [];

  const selectedDataType = column.selectedDataType || "string";

  if (column.field && column.field !== COUNT_FIELD) {
    const letter = DATA_TYPE_LETTERS[selectedDataType];
    result.push(new Literal(`${column.field}:${letter}`));
  }

  if (column.field === COUNT_FIELD) {
    result.push(new FunctionArg("aggregate", new Literal("count")));
    return result;
  }

  const aggregate = getAggregate(column.aggregate, selectedDataType);

  if (aggregate) {
    result.push(new FunctionArg("aggregate", new Literal(aggregate)));
  }

  if (column.sort) {
    result.push(new FunctionArg("sort", new Literal(column.sort)));
  }

  if (column.timeUnit) {
    result.push(new FunctionArg("timeUnit", new Literal(column.timeUnit)));
  }

  return result;
}
