/* Copyright 2024 Marimo. All rights reserved. */
import {
  FunctionCall,
  Literal,
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
      let markProps: Record<string, PythonCode> = {};

      if (typeof spec.mark === "object" && "type" in spec.mark) {
        markProps = Object.fromEntries(
          Object.entries(spec.mark)
            .filter(([key]) => key !== "type")
            .map(([key, value]) => [key, new Literal(value)]),
        );
      }

      code = code.chain(`mark_${markType}`, markProps);
    }
  }

  const hasEncodings = "encoding" in spec;
  if (hasEncodings) {
    const encodeArgs: Record<string, PythonCode> = {};
    const encodings = spec.encoding;

    if (encodings?.x) {
      const kwargs = makeKwargs(encodings.x);
      encodeArgs.x = new FunctionCall("alt.X", kwargs);
    }

    if (encodings?.y) {
      const kwargs = makeKwargs(encodings.y);
      encodeArgs.y = new FunctionCall("alt.Y", kwargs);
    }

    if (encodings?.color) {
      const kwargs = makeKwargs(encodings.color);
      encodeArgs.color = new FunctionCall("alt.Color", kwargs);
    }

    if (encodings?.theta) {
      const kwargs = makeKwargs(encodings.theta);
      encodeArgs.theta = new FunctionCall("alt.Theta", kwargs);
    }

    const hasRow = encodings && "row" in encodings;
    if (hasRow && encodings.row) {
      const kwargs = makeKwargs(encodings.row);
      encodeArgs.row = new FunctionCall("alt.Row", kwargs);
    }

    const hasColumn = encodings && "column" in encodings;
    if (hasColumn && encodings.column) {
      const kwargs = makeKwargs(encodings.column);
      encodeArgs.column = new FunctionCall("alt.Column", kwargs);
    }

    if (encodings?.tooltip) {
      const tooltip = encodings.tooltip;
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const makeTooltip = (t: Record<string, any>) => {
        const kwargs = makeKwargs(t);
        return new FunctionCall("alt.Tooltip", kwargs);
      };

      const tooltipArray = Array.isArray(tooltip)
        ? new Literal(tooltip.map(makeTooltip))
        : makeTooltip(tooltip);
      encodeArgs.tooltip = tooltipArray;
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
  const propertiesKeys = ["title", "height", "width"];
  for (const key of propertiesKeys) {
    if (key in spec) {
      propertiesArgs[key] = new Literal(spec[key as keyof VegaLiteSpec]);
    }
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

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function makeKwargs<T extends Record<string, any>>(obj: T) {
  const result: Record<string, PythonCode> = {};

  for (const [key, value] of Object.entries(obj)) {
    if (value !== undefined) {
      result[key] = new Literal(value);
    }
  }

  return result;
}
