/* Copyright 2026 Marimo. All rights reserved. */
import { Tracer } from "@/utils/tracer";

export const t = new Tracer();

// eslint-disable-next-line @typescript-eslint/no-explicit-any
(globalThis as any).t = t;
