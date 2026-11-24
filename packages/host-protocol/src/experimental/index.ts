/* Copyright 2026 Marimo. All rights reserved. */

import { makeHostContract } from "../contract.ts";
import analysis from "./features/analysis.ts";
import emit from "./features/emit.ts";

export const features = [analysis, emit] as const;
export const { Api, events } = makeHostContract(features);
