/* Copyright 2026 Marimo. All rights reserved. */
import { DefaultWasmController } from "./bootstrap";
import type { WasmController } from "./types";

// Load the controller
// Falls back to the default controller
export async function getController(version: string): Promise<WasmController> {
  // Hosts that provide a custom /wasm/controller.js opt in via the worker
  // name (see bridge.ts). Default: skip the dynamic import to avoid a
  // guaranteed-404 round trip on the standard build.
  const hasCustomController = self.name?.includes("::controller") ?? false;
  if (!hasCustomController) {
    return new DefaultWasmController();
  }
  try {
    const controller = await import(
      /* @vite-ignore */ `/wasm/controller.js?version=${version}`
    );
    return controller;
  } catch {
    return new DefaultWasmController();
  }
}
