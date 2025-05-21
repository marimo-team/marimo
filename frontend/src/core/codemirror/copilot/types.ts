/* Copyright 2024 Marimo. All rights reserved. */
/* eslint-disable @typescript-eslint/no-empty-interface */

export interface GitHubCopilotSignInInitiateResult {
  verificationUri: string; // https://github.com/login/device
  status: GitHubCopilotStatus; // PromptUserDeviceFlow
  userCode: string;
  expiresIn: number; // Seconds (usually 15 minutes)
  interval: number; // For polling
  command: {
    command: string; // github.copilot.finishDeviceFlow
    title: string; // Sign in with GitHub
    arguments: string[];
  };
}

export interface GitHubCopilotSignInConfirmParams {
  userCode: string;
}

/**
 * Copilot account status.
 */
export type GitHubCopilotStatus =
  | "SignedIn"
  | "AlreadySignedIn"
  | "MaybeOk"
  | "NotAuthorized"
  | "NotSignedIn"
  | "PromptUserDeviceFlow"
  | "OK";

/**
 * Copilot status.
 */
export type GitHubCopilotRequestStatus = "InProgress" | "Warning" | "Normal";

export interface GitHubCopilotStatusResult {
  status: GitHubCopilotStatus;
  user: string;
}
