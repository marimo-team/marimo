/* Copyright 2026 Marimo. All rights reserved. */
import type { DataURLString } from "@/utils/json/base64";
import type { ModelLifecycle } from "../kernel/messages";

export type StaticVirtualFiles = Record<string, DataURLString>;

export interface MarimoStaticState {
  files: StaticVirtualFiles;
  modelNotifications?: ModelLifecycle[];
}
