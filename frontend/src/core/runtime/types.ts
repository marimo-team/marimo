/* Copyright 2024 Marimo. All rights reserved. */

export interface RuntimeConfig {
  url: string;
  serverToken?: string; // Skew protection token
  authToken?: string | null; // API key or JWT token for remote backend
}
