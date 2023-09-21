/* Copyright 2023 Marimo. All rights reserved. */
import { getUserConfig } from "@/core/state/config";
import { atomWithStorage } from "jotai/utils";

const KEY = "marimo:copilot:signedIn";

export const copilotSignedInState = atomWithStorage<boolean | null>(KEY, null);

function getIsLastSignedIn() {
  const lastSignedIn = localStorage.getItem(KEY);
  return lastSignedIn === "true";
}

export function isCopilotEnabled() {
  const copilot = getIsLastSignedIn();
  const userConfig = getUserConfig();
  return copilot && userConfig.completion.copilot;
}
