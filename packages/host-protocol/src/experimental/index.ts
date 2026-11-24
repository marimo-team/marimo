/* Copyright 2026 Marimo. All rights reserved. */

import { makeHostContract } from "../contract.ts";
import analysis from "./features/analysis.ts";

export const { Api, events } = makeHostContract([analysis]);
