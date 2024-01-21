/* Copyright 2024 Marimo. All rights reserved. */
import { setupWorker } from "msw";
import { handlers } from "./handlers";
import { createMockServer } from "./socket";

// Create a mock server for the WebSocket connection.
if (import.meta.env.DEV && import.meta.env.VITE_MSW) {
  createMockServer();
}

// This configures a Service Worker with the given request handlers.
export const worker = setupWorker(...handlers);
