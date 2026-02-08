/* Copyright 2026 Marimo. All rights reserved. */
import type { DataURLString } from "@/utils/json/base64";
import type { ModelLifecycle } from "../kernel/messages";

type ModelOpenMessage = Extract<ModelLifecycle["message"], { method: "open" }>;

export type StaticVirtualFiles = Record<string, DataURLString>;

// NB: Static model state is represented as synthetic aggregated
// "open" events that we replay on page load.
export type StaticModelState = Omit<ModelOpenMessage, "method">;

export interface MarimoStaticState {
  files: StaticVirtualFiles;
  modelStates?: Record<string, StaticModelState>;
}
