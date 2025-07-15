/* Copyright 2024 Marimo. All rights reserved. */

import { cleanup } from "@testing-library/react";
import { afterEach, beforeEach, vi } from "vitest";
import "@testing-library/jest-dom/vitest";
import "blob-polyfill";

// Global setup for all tests
beforeEach(() => {
  // Reset all mocks before each test
  vi.clearAllMocks();
});

// Cleanup after each test case (e.g., clearing jsdom)
afterEach(() => {
  cleanup();
});
