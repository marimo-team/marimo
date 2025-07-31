/* Copyright 2024 Marimo. All rights reserved. */

import type { Field } from "vega-lite/build/src/channeldef";
import type { Encoding } from "vega-lite/build/src/encoding";
import type {
  GenericUnitSpec,
  TopLevelUnitSpec,
} from "vega-lite/build/src/spec/unit";

export type { TopLevelSpec as VegaLiteSpec } from "vega-lite";
export type { SingleDefUnitChannel } from "vega-lite/build/src/channel";
export type { Field } from "vega-lite/build/src/channeldef";
export type { SharedCompositeEncoding } from "vega-lite/build/src/compositemark";
export type { DataFormat } from "vega-lite/build/src/data";
export type { AnyMark, MarkDef } from "vega-lite/build/src/mark";
export { Mark } from "vega-lite/build/src/mark";
export type {
  SelectionParameter,
  SelectionType,
} from "vega-lite/build/src/selection";
export type {
  FacetedUnitSpec,
  GenericFacetSpec,
  LayerSpec,
  UnitSpec,
} from "vega-lite/build/src/spec";

export type VegaLiteUnitSpec = TopLevelUnitSpec<Field>;
// eslint-disable-next-line @typescript-eslint/no-explicit-any
export type GenericVegaSpec = GenericUnitSpec<any, any, any>;
export type EncodingType = keyof Encoding<Field>;
export type Encodings = Encoding<Field>;
