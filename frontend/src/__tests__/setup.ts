/* Copyright 2024 Marimo. All rights reserved. */
import "@testing-library/jest-dom/vitest";
import { afterEach } from "vitest";
import { cleanup } from "@testing-library/react";
import "blob-polyfill";

declare module "vitest" {
  interface Assertion {
    toBeInTheDocument(): void;
    toHaveTextContent(text: string): void;
    toBeVisible(): void;
  }
}

// Cleanup after each test case (e.g., clearing jsdom)
afterEach(() => {
  cleanup();
});
