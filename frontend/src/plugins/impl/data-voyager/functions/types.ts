/* Copyright 2023 Marimo. All rights reserved. */
import { FieldQueryBase } from "compassql/build/src/query/encoding";

type AggregateOp = Extract<FieldQueryBase["aggregate"], string>;
export type TimeUnitOp = Extract<FieldQueryBase["timeUnit"], string>;

export type FieldFunction = AggregateOp | "bin" | TimeUnitOp;
