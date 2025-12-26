/* Copyright 2026 Marimo. All rights reserved. */

import { atom } from "jotai";
import { atomWithStorage } from "jotai/utils";
import {
  getResolvedMarimoConfig,
  resolvedMarimoConfigAtom,
} from "@/core/config/config";
import { store, waitFor } from "@/core/state/jotai";
import { jotaiJsonStorage } from "@/utils/storage/jotai";
import { availableStorage } from "@/utils/storage/storage";
import type { GitHubCopilotStatusNotificationParams } from "./types";

const KEY = "marimo:copilot:signedIn";

export const isGitHubCopilotSignedInState = atomWithStorage<boolean | null>(
  KEY,
  null,
  jotaiJsonStorage,
  {
    getOnInit: true,
  },
);

type Step =
  | "signedIn"
  | "signingIn"
  | "signInFailed"
  | "signedOut"
  | "connecting"
  | "connectionError"
  | "notConnected";

export const copilotSignedInState = atom<Step | null>(null);

export const githubCopilotLoadingVersion = atom<number | null>(null);

export const copilotStatusState = atom<GitHubCopilotStatusNotificationParams>({
  busy: false,
  kind: null,
  message: null,
});

/**
 * Set the currently loading document version
 */
export function setGitHubCopilotLoadingVersion(version: number) {
  store.set(githubCopilotLoadingVersion, version);
}
/**
 * Clear the currently loading document version, if it matches the current version
 */
export function clearGitHubCopilotLoadingVersion(expectedVersion: number) {
  const currentVersion = store.get(githubCopilotLoadingVersion);
  if (currentVersion === expectedVersion) {
    store.set(githubCopilotLoadingVersion, null);
  }
}

function getIsLastSignedIn() {
  const lastSignedIn = availableStorage.getItem(KEY);
  return lastSignedIn === "true";
}

export function isCopilotEnabled() {
  const copilot = getIsLastSignedIn();
  const userConfig = getResolvedMarimoConfig();
  return copilot && userConfig.completion.copilot === "github";
}

export function waitForEnabledCopilot() {
  return waitFor(resolvedMarimoConfigAtom, (value) => {
    return value.completion.copilot === "github";
  });
}
