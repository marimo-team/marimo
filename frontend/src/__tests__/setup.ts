/* Copyright 2026 Marimo. All rights reserved. */

import { cleanup } from "@testing-library/react";
import { afterEach, beforeEach, vi } from "vitest";
import "@testing-library/jest-dom/vitest";
import "blob-polyfill";

// mock implementation because jsdom doesn't support ResizeObserver
// if we need to test ResizeObserver functionality
// we can use a library like "resize-observer-polyfill"
globalThis.ResizeObserver ??= class {
  public observe(_target: Element) {
    /* noop */
  }
  public unobserve(_target: Element) {
    /* noop */
  }
  public disconnect() {
    /* noop */
  }
} as never;

// mock implementation because jsdom doesn't support IntersectionObserver
globalThis.IntersectionObserver ??= class {
  public observe(_target: Element) {
    /* noop */
  }
  public unobserve(_target: Element) {
    /* noop */
  }
  public disconnect() {
    /* noop */
  }
  public takeRecords() {
    return [];
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
