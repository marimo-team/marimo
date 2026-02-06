/* Copyright 2026 Marimo. All rights reserved. */
import type { Base64String, DataURLString } from "@/utils/json/base64";

export type StaticVirtualFiles = Record<string, DataURLString>;

export interface StaticModelState {
  state: Record<string, unknown>;
  buffer_paths: (string | number)[][];
  buffers: Base64String[];
}

export interface MarimoStaticState {
  files: StaticVirtualFiles;
  modelStates?: Record<string, StaticModelState>;
}
