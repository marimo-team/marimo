/* Copyright 2023 Marimo. All rights reserved. */
import type { TopLevelUnitSpec } from "vega-lite/build/src/spec/unit";
import type { Encoding } from "vega-lite/build/src/encoding";
import type { Field } from "vega-lite/build/src/channeldef";

export type { SharedCompositeEncoding } from "vega-lite/build/src/compositemark";
export type { AnyMark } from "vega-lite/build/src/mark";
export { Mark } from "vega-lite/build/src/mark";
export type { TopLevelSpec as VegaLiteSpec } from "vega-lite";
export { type Field } from "vega-lite/build/src/channeldef";
export type { SingleDefUnitChannel } from "vega-lite/build/src/channel";
export type {
  SelectionParameter,
  SelectionType,
} from "vega-lite/build/src/selection";

export type VegaLiteUnitedSpec = TopLevelUnitSpec<Field>;
export type EncodingType = keyof Encoding<Field>;
export type Encodings = Encoding<Field>;
