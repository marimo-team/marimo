/* Copyright 2024 Marimo. All rights reserved. */
import "@testing-library/jest-dom/vitest";
import { expect, afterEach } from "vitest";
import { cleanup } from "@testing-library/react";
import "blob-polyfill";

declare module "vitest" {
  interface Assertion<T = any> {
    toBeInTheDocument(): T;
    toHaveTextContent(text: string): T;
    toBeVisible(): T;
  }
}

// Cleanup after each test case (e.g., clearing jsdom)
afterEach(() => {
  cleanup();
});
