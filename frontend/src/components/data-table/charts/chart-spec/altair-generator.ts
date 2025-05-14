/* Copyright 2024 Marimo. All rights reserved. */
import {
  FunctionCall,
  Literal,
  objectsToPythonCode,
  type PythonCode,
  Variable,
  VariableDeclaration,
} from "@/utils/python-poet/poet";

import type { VegaLiteSpec } from "@/plugins/impl/vega/types";

/**
 * Generates Python code for an Altair chart.
 */
export function generateAltairChart(
  spec: VegaLiteSpec,
  datasource: string,
): PythonCode {
  let code = new FunctionCall("alt.Chart", [new Variable(datasource)], true);

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
    const encodeArgs: Record<string, PythonCode> = {};
    const encodings = spec.encoding;

    if (encodings?.x) {
      const xCode = objectsToPythonCode([encodings.x], "alt.X");
      encodeArgs.x = xCode;
    }

    if (encodings?.y) {
      encodeArgs.y = objectsToPythonCode([encodings.y], "alt.Y");
    }

    if (encodings?.color) {
      encodeArgs.color = objectsToPythonCode([encodings.color], "alt.Color");
    }

    const hasRow = encodings && "row" in encodings;
    if (hasRow && encodings.row) {
      encodeArgs.row = objectsToPythonCode([encodings.row], "alt.Row");
    }

    const hasColumn = encodings && "column" in encodings;
    if (hasColumn && encodings.column) {
      encodeArgs.column = objectsToPythonCode([encodings.column], "alt.Column");
    }

    if (encodings?.tooltip) {
      const tooltip = encodings.tooltip;
      const tooltipArray = Array.isArray(tooltip) ? tooltip : [tooltip];
      const tooltipCode = objectsToPythonCode(tooltipArray, "alt.Tooltip");
      encodeArgs.tooltip = tooltipCode;
    }

    code = code.chain("encode", encodeArgs);
  }

  if (spec.resolve) {
    const resolve = spec.resolve;
    const axisArgs: Record<string, PythonCode> = {};

    if (resolve.axis?.x) {
      axisArgs.x = new Literal(resolve.axis.x);
    }

    if (resolve.axis?.y) {
      axisArgs.y = new Literal(resolve.axis.y);
    }

    code = code.chain("resolve_scale", axisArgs);
  }

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
