/* Copyright 2024 Marimo. All rights reserved. */
import { getUserConfig, userConfigAtom } from "@/core/config/config";
import { store, waitFor } from "@/core/state/jotai";
import { atom } from "jotai";
import { atomWithStorage } from "jotai/utils";

const KEY = "marimo:copilot:signedIn";

export const isGitHubCopilotSignedInState = atomWithStorage<boolean | null>(
  KEY,
  null,
  undefined,
  {
    getOnInit: true,
  },
);

export const githubCopilotLoadingVersion = atom<number | null>(null);

/**
 * Set the currently loading document version
 */
export function setGitHubCopilotStartLoadingVersion(version: number) {
  store.set(githubCopilotLoadingVersion, version);
}
/**
 * Clear the currently loading document version, if it matches the current version
 */
export function clearGitHubCopilotStopLoadingVersion(expectedVersion: number) {
  const currentVersion = store.get(githubCopilotLoadingVersion);
  if (currentVersion === expectedVersion) {
    store.set(githubCopilotLoadingVersion, null);
  }
}

function getIsLastSignedIn() {
  const lastSignedIn = localStorage.getItem(KEY);
  return lastSignedIn === "true";
}

export function isCopilotEnabled() {
  const copilot = getIsLastSignedIn();
  const userConfig = getUserConfig();
  return copilot && userConfig.completion.copilot === "github";
}

export function waitForEnabledCopilot() {
  return waitFor(userConfigAtom, (value) => {
    return value.completion.copilot === "github";
  });
}
