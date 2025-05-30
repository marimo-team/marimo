/* Copyright 2024 Marimo. All rights reserved. */
import type { DataURLString } from "@/utils/json/base64";

export type StaticVirtualFiles = Record<string, DataURLString>;

export interface MarimoStaticState {
  files: StaticVirtualFiles;
}
