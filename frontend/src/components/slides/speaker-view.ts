/* Copyright 2026 Marimo. All rights reserved. */

import type { RuntimeKind } from "@/core/runtime/adapter";

export function createSpeakerViewUrl(href: string): string {
  const url = new URL(href);
  url.hash = "";
  url.searchParams.set("kiosk", "true");
  url.searchParams.set("show-chrome", "false");
  return url.toString();
}

export function isSpeakerViewReceiver(
  kioskMode: boolean,
  search: string,
): boolean {
  return kioskMode && new URLSearchParams(search).has("receiver");
}

export function supportsSpeakerView(runtimeKind: RuntimeKind): boolean {
  return runtimeKind !== "wasm";
}
