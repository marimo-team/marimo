/* Copyright 2024 Marimo. All rights reserved. */

import { get } from "lodash-es";

export interface PlotlyTemplateParser {
  /**
   * Update the parser with a new hover template, if needed.
   */
  update(newTemplate: string): PlotlyTemplateParser;
  /**
   * Given a Plotly.PlotDatum, parse the data and return an object with the key-value pairs.
   */
  parse(data: Plotly.PlotDatum): Record<string, string>;
}

/**
 * Hover template looks something like this:
 *   "Origin=%{customdata[1]}<br>Horsepower=%{x}<br>Miles_per_Gallon=%{y}<br>Weight_in_lbs=%{marker.size}<br>Name=%{customdata[0]}<extra></extra>"
 *
 * We want to parse the keys/selectors to get the values for each data point.
 *
 * NOTE: This is a very naive implementation.
 * It only works for hover templates that have the pattern key=%{selector}.
 */
export function createParser(hovertemplate: string): PlotlyTemplateParser {
  // Regular expression to match the pattern key=%{selector}
  const regex = /(\w+)=%{([^}]+)}/g;

  // Create an object to hold the key-selector pairs
  const keySelectorPairs: Record<string, string> = {};

  let match: RegExpExecArray | null;

  // Use exec to find all occurrences of the pattern and iterate over them
  while ((match = regex.exec(hovertemplate)) !== null) {
    // match[1] is the key, match[2] is the selector
    keySelectorPairs[match[1]] = match[2];
  }

  return {
    update(newTemplate: string): PlotlyTemplateParser {
      // If the template hasn't changed, return the same parser
      if (newTemplate === hovertemplate) {
        return this;
      }
      return createParser(newTemplate);
    },
    parse(data: Plotly.PlotDatum) {
      return Object.entries(keySelectorPairs).reduce<Record<string, string>>(
        (acc, [key, selector]) => {
          acc[key] = get(data, selector);
          return acc;
        },
        {},
      );
    },
  };
}
