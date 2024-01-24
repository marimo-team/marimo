/* Copyright 2024 Marimo. All rights reserved. */
/* eslint-disable @typescript-eslint/no-empty-interface */

export interface CopilotSignInInitiateParams {}
export interface CopilotSignInInitiateResult {
  verificationUri: string;
  status: string;
  userCode: string;
  expiresIn: number;
  interval: number;
}
export interface CopilotSignInConfirmParams {
  userCode: string;
}
export type CopilotStatus =
  | "SignedIn"
  | "AlreadySignedIn"
  | "MaybeOk"
  | "NotAuthorized"
  | "NotSignedIn"
  | "OK";
export interface CopilotSignInConfirmResult {
  status: CopilotStatus;
  user: string;
}
export interface CopilotSignOutParams {}
export interface CopilotSignOutResult {
  status: CopilotStatus;
}
export interface CopilotGetCompletionsParams {
  doc: {
    source: string;
    tabSize: number;
    indentSize: number;
    insertSpaces: boolean;
    path: string;
    uri: string;
    relativePath: string;
    languageId: string;
    version: number;
    position: {
      line: number;
      character: number;
    };
  };
}
export interface CopilotGetCompletionsResult {
  completions: Array<{
    text: string;
    position: {
      line: number;
      character: number;
    };
    uuid: string;
    range: {
      start: {
        line: number;
        character: number;
      };
      end: {
        line: number;
        character: number;
      };
    };
    displayText: string;
    point: {
      line: number;
      character: number;
    };
    region: {
      start: {
        line: number;
        character: number;
      };
      end: {
        line: number;
        character: number;
      };
    };
  }>;
}
export interface CopilotAcceptCompletionParams {
  uuid: string;
}
export interface CopilotRejectCompletionParams {
  uuids: string[];
}
