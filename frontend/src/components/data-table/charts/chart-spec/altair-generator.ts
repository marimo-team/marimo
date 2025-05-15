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
    const markType =
      typeof spec.mark === "string" ? spec.mark : spec.mark?.type;

    if (markType) {
      const markProps =
        typeof spec.mark === "object" && "type" in spec.mark
          ? Object.fromEntries(
              Object.entries(spec.mark)
                .filter(([key]) => key !== "type")
                .map(([key, value]) => [key, new Literal(value)]),
            )
          : {};

      code = code.chain(
        `mark_${markType}`,
        Object.keys(markProps).length > 0 ? markProps : [],
      );
    }
  }

  const hasEncodings = "encoding" in spec;
  if (hasEncodings) {
    const encodeArgs: Record<string, PythonCode> = {};
    const encodings = spec.encoding;

    if (encodings?.x) {
      encodeArgs.x = new FunctionCall("alt.X", [
        new Literal(encodings.x, { objectAsFieldNames: true }),
      ]);
    }

    if (encodings?.y) {
      encodeArgs.y = new FunctionCall("alt.Y", [
        new Literal(encodings.y, { objectAsFieldNames: true }),
      ]);
    }

    if (encodings?.color) {
      encodeArgs.color = new FunctionCall("alt.Color", [
        new Literal(encodings.color, { objectAsFieldNames: true }),
      ]);
    }

    if (encodings?.theta) {
      encodeArgs.theta = new FunctionCall("alt.Theta", [
        new Literal(encodings.theta, { objectAsFieldNames: true }),
      ]);
    }

    const hasRow = encodings && "row" in encodings;
    if (hasRow && encodings.row) {
      encodeArgs.row = new FunctionCall("alt.Row", [
        new Literal(encodings.row, { objectAsFieldNames: true }),
      ]);
    }

    const hasColumn = encodings && "column" in encodings;
    if (hasColumn && encodings.column) {
      encodeArgs.column = new FunctionCall("alt.Column", [
        new Literal(encodings.column, { objectAsFieldNames: true }),
      ]);
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

  const propertiesArgs: Record<string, PythonCode> = {};
  if (spec.title) {
    propertiesArgs.title = new Literal(spec.title);
  }
  if ("height" in spec) {
    propertiesArgs.height = new Literal(spec.height);
  }
  if ("width" in spec) {
    propertiesArgs.width = new Literal(spec.width);
  }

  if (Object.keys(propertiesArgs).length > 0) {
    code = code.chain("properties", propertiesArgs);
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
