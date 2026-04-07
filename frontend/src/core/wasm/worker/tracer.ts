/* Copyright 2026 Marimo. All rights reserved. */
import { Tracer } from "@/utils/tracer";

export const t = new Tracer();

// oxlint-disable-next-line typescript/no-explicit-any
(globalThis as any).t = t;
