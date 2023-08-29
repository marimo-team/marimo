/* Copyright 2023 Marimo. All rights reserved. */
import { store } from "@/core/jotai";
import { atomWithReducer } from "jotai/utils";

interface CopilotState {
  /**
   * null means we don't know yet
   */
  copilotSignedIn: boolean | null;
  copilotEnabled: boolean;
}

type Action =
  | { type: "signedIn"; signedIn: boolean }
  | { type: "copilotEnabled"; enabled: boolean };

export const copilotState = atomWithReducer<CopilotState, Action>(
  {
    copilotSignedIn: null,
    copilotEnabled: false,
  },
  (prev, action) => {
    if (!action) {
      return prev;
    }

    switch (action.type) {
      case "signedIn":
        return { ...prev, copilotSignedIn: action.signedIn };
      case "copilotEnabled":
        return { ...prev, copilotEnabled: action.enabled };
      default:
        return prev;
    }
  }
);

export function isCopilotEnabled() {
  const copilot = store.get(copilotState);
  return copilot.copilotSignedIn && copilot.copilotEnabled;
}
