/* Copyright 2023 Marimo. All rights reserved. */
import { getUserConfig } from "@/core/state/config";
import { store } from "@/core/state/jotai";
import { atomWithStorage } from "jotai/utils";

export const copilotSignedInState = atomWithStorage<boolean | null>(
  "marimo:copilot:signedIn",
  null
);

export function isCopilotEnabled() {
  const copilot = store.get(copilotSignedInState);
  const userConfig = getUserConfig();
  return copilot && userConfig.completion.copilot;
}
