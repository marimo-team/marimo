/* Copyright 2024 Marimo. All rights reserved. */
import { SpecQuery } from "compassql/build/src/query/spec";
import { SHORT_WILDCARD } from "compassql/build/src/wildcard";

export type SpecMark = SpecQuery["mark"] | SHORT_WILDCARD;

export const MARKS = [
  SHORT_WILDCARD,
  "area",
  "bar",
  "circle",
  "geoshape",
  "line",
  "point",
  "rect",
  "rule",
  "square",
  "text",
  "tick",
  "trail",
] as const;
