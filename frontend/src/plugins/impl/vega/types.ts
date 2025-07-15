/* Copyright 2024 Marimo. All rights reserved. */

import type { Field } from "vega-lite/types_unstable/channeldef.js";
import type { Encoding } from "vega-lite/types_unstable/encoding.js";
import type {
  GenericUnitSpec,
  TopLevelUnitSpec,
} from "vega-lite/types_unstable/spec/unit.js";

export type { TopLevelSpec as VegaLiteSpec } from "vega-lite";
export type { SingleDefUnitChannel } from "vega-lite/types_unstable/channel.js";
export type { Field } from "vega-lite/types_unstable/channeldef.js";
export type { SharedCompositeEncoding } from "vega-lite/types_unstable/compositemark/index.js";
export type { DataFormat } from "vega-lite/types_unstable/data.js";
export type { AnyMark, MarkDef } from "vega-lite/types_unstable/mark.js";
export { Mark } from "vega-lite/types_unstable/mark.js";
export type {
  SelectionParameter,
  SelectionType,
} from "vega-lite/types_unstable/selection.js";
export type { GenericFacetSpec } from "vega-lite/types_unstable/spec/facet.js";
export type { LayerSpec } from "vega-lite/types_unstable/spec/layer.js";
export type {
  FacetedUnitSpec,
  UnitSpec,
} from "vega-lite/types_unstable/spec/unit.js";

export type VegaLiteUnitSpec = TopLevelUnitSpec<Field>;
// eslint-disable-next-line @typescript-eslint/no-explicit-any
export type GenericVegaSpec = GenericUnitSpec<any, any, any>;
export type EncodingType = keyof Encoding<Field>;
export type Encodings = Encoding<Field>;
