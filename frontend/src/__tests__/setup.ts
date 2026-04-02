/* Copyright 2026 Marimo. All rights reserved. */

import { cleanup } from "@testing-library/react";
import { afterEach, beforeEach, vi } from "vitest";
import "@testing-library/jest-dom/vitest";
import "blob-polyfill";

// mock implementation because jsdom doesn't support ResizeObserver
// if we need to test ResizeObserver functionality
// we can use a library like "resize-observer-polyfill"
globalThis.ResizeObserver ??= class {
  observe(_target: Element) {
    /* noop */
  }
  unobserve(_target: Element) {
    /* noop */
  }
  disconnect() {
    /* noop */
  }
} as never;

// Global setup for all tests
beforeEach(() => {
  // Reset all mocks before each test
  vi.clearAllMocks();
});

// Cleanup after each test case (e.g., clearing jsdom)
afterEach(() => {
  cleanup();
});
