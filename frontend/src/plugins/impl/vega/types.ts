/* Copyright 2024 Marimo. All rights reserved. */
import type {
  TopLevelUnitSpec,
  GenericUnitSpec,
} from "vega-lite/build/src/spec/unit";
import type { Encoding } from "vega-lite/build/src/encoding";
import type { Field } from "vega-lite/build/src/channeldef";

export type { SharedCompositeEncoding } from "vega-lite/build/src/compositemark";
export type { AnyMark, MarkDef } from "vega-lite/build/src/mark";
export { Mark } from "vega-lite/build/src/mark";
export type { TopLevelSpec as VegaLiteSpec } from "vega-lite";
export { type Field } from "vega-lite/build/src/channeldef";
export type { SingleDefUnitChannel } from "vega-lite/build/src/channel";
export type {
  SelectionParameter,
  SelectionType,
} from "vega-lite/build/src/selection";
export type { DataFormat } from "vega-lite/build/src/data";
export type {
  LayerSpec,
  UnitSpec,
  GenericFacetSpec,
  FacetedUnitSpec,
} from "vega-lite/build/src/spec";

export type VegaLiteUnitSpec = TopLevelUnitSpec<Field>;
// eslint-disable-next-line @typescript-eslint/no-explicit-any
export type GenericVegaSpec = GenericUnitSpec<any, any, any>;
export type EncodingType = keyof Encoding<Field>;
export type Encodings = Encoding<Field>;
