/* Copyright 2024 Marimo. All rights reserved. */
import { afterEach } from "vitest";
import { cleanup } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import "blob-polyfill";

// Cleanup after each test case (e.g., clearing jsdom)
afterEach(() => {
  cleanup();
});
