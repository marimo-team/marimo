/* Copyright 2024 Marimo. All rights reserved. */
import { getUserConfig, userConfigAtom } from "@/core/config/config";
import { waitFor } from "@/core/state/jotai";
import { atomWithStorage } from "jotai/utils";

const KEY = "marimo:copilot:signedIn";

export const copilotSignedInState = atomWithStorage<boolean | null>(
  KEY,
  null,
  undefined,
  {
    getOnInit: true,
  },
);

function getIsLastSignedIn() {
  const lastSignedIn = localStorage.getItem(KEY);
  return lastSignedIn === "true";
}

export function isCopilotEnabled() {
  const copilot = getIsLastSignedIn();
  const userConfig = getUserConfig();
  return copilot && userConfig.completion.copilot;
}

export function waitForEnabledCopilot() {
  return waitFor(userConfigAtom, (value) => {
    return value.completion.copilot;
  });
}
