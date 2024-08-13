/* Copyright 2024 Marimo. All rights reserved. */
export const Constants = {
  githubPage: "https://github.com/marimo-team/marimo",
  issuesPage: "https://github.com/marimo-team/marimo/issues",
};

export const KnownQueryParams = {
  /**
   * When in read mode, if the code should be shown by default
   */
  showCode: "show-code",
  /**
   * When in read mode, if the code should be hidden by default
   */
  includeCode: "include-code",
  /**
   * Session ID for the current notebook
   */
  sessionId: "session_id",
  /**
   * Kiosk mode. If the editor is running in kiosk mode
   */
  kiosk: "kiosk",
  /**
   * VSCode mode. If the editor is running inside VSCode
   */
  vscode: "vscode",
  /**
   * File path of the current notebook
   */
  filePath: "file",
  /**
   * Access token for the current user
   */
  accessToken: "access_token",
  /**
   * Layout view-as. If the editor is in run-mode, this overrides the current
   * layout view.
   */
  viewAs: "view-as",
};
