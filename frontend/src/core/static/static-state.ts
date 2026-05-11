/* Copyright 2026 Marimo. All rights reserved. */
import { invariant } from "@/utils/invariant";
import type { ModelLifecycle } from "../kernel/messages";
import type { MarimoStaticState, StaticVirtualFiles } from "./types";

declare global {
  interface Window {
    __MARIMO_STATIC__?: Readonly<MarimoStaticState>;
  }
}

function isStringToStringRecord(
  value: unknown,
): value is Record<string, string> {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    return false;
  }
  for (const entry of Object.values(value)) {
    if (typeof entry !== "string") {
      return false;
    }
  }
  return true;
}

function isMarimoStaticState(
  value: unknown,
): value is Readonly<MarimoStaticState> {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    return false;
  }
  const candidate = value as MarimoStaticState;
  if (!isStringToStringRecord(candidate.files)) {
    return false;
  }
  if (
    candidate.modelNotifications !== undefined &&
    !Array.isArray(candidate.modelNotifications)
  ) {
    return false;
  }
  return true;
}

function getMarimoStaticState(): Readonly<MarimoStaticState> | undefined {
  // `typeof window` guard handles the identifier-undeclared case (e.g.
  // leaked async work firing after jsdom teardown in tests); `?.` only
  // short-circuits on null/undefined.
  const state =
    typeof window === "undefined" ? undefined : window.__MARIMO_STATIC__;
  return isMarimoStaticState(state) ? state : undefined;
}

export function isStaticNotebook(): boolean {
  return getMarimoStaticState() !== undefined;
}

export function getStaticVirtualFiles(): StaticVirtualFiles {
  const state = getMarimoStaticState();
  invariant(state !== undefined, "Not a static notebook");
  return state.files;
}

export function getStaticModelNotifications(): ModelLifecycle[] | undefined {
  return getMarimoStaticState()?.modelNotifications;
}
