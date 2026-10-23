/* Copyright 2026 Marimo. All rights reserved. */

export interface RuntimeConfig {
  /**
   * The URL of the runtime server.
   */
  url: string;
  /**
   * If true, the runtime will not be loaded until the user interacts with the notebook.
   * If false, the runtime will be loaded immediately.
   */
  readonly lazy: boolean;
  /**
   * The server token for the runtime (Skew protection token)
   */
  readonly serverToken?: string;
  /**
   * The API key or JWT token for the remote backend (used for authentication)
   */
  readonly authToken?: string | null;
}
