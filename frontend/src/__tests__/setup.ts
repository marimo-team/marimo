/* Copyright 2024 Marimo. All rights reserved. */

import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";
import "@testing-library/jest-dom/vitest";
import "blob-polyfill";

// Cleanup after each test case (e.g., clearing jsdom)
afterEach(() => {
  cleanup();
});
