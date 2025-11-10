/* Copyright 2024 Marimo. All rights reserved. */

import { type RenderOptions, render } from "@testing-library/react";
import { createStore, Provider } from "jotai";
import type { ReactElement } from "react";
import {
  ISLAND_DATA_ATTRIBUTES,
  ISLAND_TAG_NAMES,
} from "@/core/islands/constants";

/**
 * Test utilities for islands components and logic
 */

// ============================================================================
// DOM Test Utilities
// ============================================================================

/**
 * Creates a mock marimo-island element in the DOM
 */
export function createMockIslandElement(options: {
  appId?: string;
  cellIdx?: string;
  code?: string;
  innerHTML?: string;
}): HTMLElement {
  const {
    appId = "test-app",
    cellIdx = "0",
    code = "import marimo as mo",
    innerHTML = "",
  } = options;

  const element = document.createElement(ISLAND_TAG_NAMES.ISLAND);
  element.setAttribute(ISLAND_DATA_ATTRIBUTES.APP_ID, appId);
  element.setAttribute(ISLAND_DATA_ATTRIBUTES.CELL_IDX, cellIdx);

  if (code) {
    const codeElement = document.createElement(ISLAND_TAG_NAMES.CELL_CODE);
    codeElement.textContent = encodeURIComponent(code);
    element.appendChild(codeElement);
  }

  if (innerHTML) {
    const outputElement = document.createElement(ISLAND_TAG_NAMES.CELL_OUTPUT);
    outputElement.innerHTML = innerHTML;
    element.appendChild(outputElement);
  }

  return element;
}

/**
 * Creates multiple island elements for testing
 */
export function createMockIslands(
  count: number,
  appId = "test-app",
): HTMLElement[] {
  return Array.from({ length: count }, (_, idx) =>
    createMockIslandElement({
      appId,
      cellIdx: String(idx),
      code: `cell_${idx} = ${idx}`,
      innerHTML: `<div>output ${idx}</div>`,
    }),
  );
}

// ============================================================================
// React Test Utilities
// ============================================================================

interface IslandsRenderOptions extends Omit<RenderOptions, "wrapper"> {
  initialStore?: ReturnType<typeof createStore>;
}

/**
 * Renders a React component with Islands providers
 */
export function renderWithIslandsProviders(
  ui: ReactElement,
  options?: IslandsRenderOptions,
) {
  const { initialStore, ...renderOptions } = options || {};
  const store = initialStore || createStore();

  function Wrapper({ children }: { children: React.ReactNode }) {
    return <Provider store={store}>{children}</Provider>;
  }

  return {
    store,
    ...render(ui, { wrapper: Wrapper, ...renderOptions }),
  };
}

// ============================================================================
// Assertion Helpers
// ============================================================================

/**
 * Waits for a condition to be true with timeout
 */
export async function waitForCondition(
  condition: () => boolean,
  timeout = 1000,
  interval = 50,
): Promise<void> {
  const startTime = Date.now();
  while (!condition()) {
    if (Date.now() - startTime > timeout) {
      throw new Error("Timeout waiting for condition");
    }
    await new Promise((resolve) => setTimeout(resolve, interval));
  }
}

/**
 * Waits for an async function to not throw
 */
export async function waitForNoError<T>(
  fn: () => T | Promise<T>,
  timeout = 1000,
): Promise<T> {
  const startTime = Date.now();
  let lastError: Error | undefined;

  while (Date.now() - startTime < timeout) {
    try {
      return await Promise.resolve(fn());
    } catch (error) {
      lastError = error as Error;
      await new Promise((resolve) => setTimeout(resolve, 50));
    }
  }

  throw lastError || new Error("Timeout waiting for function to succeed");
}
