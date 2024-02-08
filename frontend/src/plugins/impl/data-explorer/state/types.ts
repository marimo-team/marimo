/* Copyright 2024 Marimo. All rights reserved. */
import type { Schema } from "compassql/build/src/schema";
import type { SpecificEncoding } from "../encoding";
import type { SpecQuery } from "compassql/build/src/query/spec";
import type { SpecMark } from "../marks";

export interface ChartSpec {
  /**
   * The type of the mark.
   */
  mark: SpecMark;

  /**
   * Mapping between specific encoding channels and encoding definitions.
   */
  encoding: SpecificEncoding;

  /**
   * Configuration of the chart.
   */
  config: SpecQuery["config"];

  /**
   * The schema for the data.
   */
  schema?: Schema | null;
}
