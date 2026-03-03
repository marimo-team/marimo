/* Copyright 2026 Marimo. All rights reserved. */
import { invariant } from "@/utils/invariant";
import type { ModelLifecycle } from "../kernel/messages";
import type { MarimoStaticState, StaticVirtualFiles } from "./types";

declare global {
  interface Window {
    __MARIMO_STATIC__?: MarimoStaticState;
  }
}

export function isStaticNotebook(): boolean {
  return window?.__MARIMO_STATIC__ !== undefined;
}

export function getStaticVirtualFiles(): StaticVirtualFiles {
  invariant(window.__MARIMO_STATIC__ !== undefined, "Not a static notebook");

  return window.__MARIMO_STATIC__.files;
}

export function getStaticModelNotifications(): ModelLifecycle[] | undefined {
  return window?.__MARIMO_STATIC__?.modelNotifications;
}
