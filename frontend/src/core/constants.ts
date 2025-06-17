/* Copyright 2024 Marimo. All rights reserved. */
export const Constants = {
  githubPage: "https://github.com/marimo-team/marimo",
  releasesPage: "https://github.com/marimo-team/marimo/releases",
  issuesPage: "https://github.com/marimo-team/marimo/issues",
  feedbackForm: "https://marimo.io/feedback",
  discordLink: "https://marimo.io/discord?ref=notebook",
  docsPage: "https://docs.marimo.io",
  youtube: "https://www.youtube.com/@marimo-team",
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
  /**
   * Show the chrome in edit mode.
   * If true, the chrome will be shown.
   * If false, the chrome will be hidden.
   */
  showChrome: "show-chrome",
  /**
   * Start in app view mode.
   * If true, the notebook will start in app view (present mode).
   * If false, the notebook will start in edit mode.
   */
  appView: "app-view",
};
