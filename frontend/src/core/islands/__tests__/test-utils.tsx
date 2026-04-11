/* Copyright 2026 Marimo. All rights reserved. */

import { type RenderOptions, render } from "@testing-library/react";
import { createStore, Provider } from "jotai";
import type { ReactElement } from "react";
import {
  ISLAND_DATA_ATTRIBUTES,
  ISLAND_TAG_NAMES,
} from "@/core/islands/constants";
import type { WorkerFactory } from "@/core/islands/worker-factory";

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

// ============================================================================
// HTML-based Island Harness
// ============================================================================

export interface IslandSpec {
  appId?: string;
  reactive?: boolean;
  code?: string;
  output?: string;
  displayCode?: boolean;
}

/**
 * Builds island HTML from a declarative spec — mirrors what generate.py produces.
 * Use with `createIslandHarness()` to parse and inspect the resulting state.
 */
export function buildIslandHTML(islands: IslandSpec[]): string {
  return islands
    .map((spec) => {
      const appId = spec.appId ?? "test-app";
      const reactive = spec.reactive ?? true;
      const output = spec.output ?? "<div>output</div>";
      const code = spec.code ?? 'print("hello")';

      const codeTag = code
        ? `<${ISLAND_TAG_NAMES.CELL_CODE}>${encodeURIComponent(code)}</${ISLAND_TAG_NAMES.CELL_CODE}>`
        : "";
      const outputTag = `<${ISLAND_TAG_NAMES.CELL_OUTPUT}>${output}</${ISLAND_TAG_NAMES.CELL_OUTPUT}>`;

      return `<${ISLAND_TAG_NAMES.ISLAND} ${ISLAND_DATA_ATTRIBUTES.APP_ID}="${appId}" ${ISLAND_DATA_ATTRIBUTES.REACTIVE}="${reactive}">${outputTag}${codeTag}</${ISLAND_TAG_NAMES.ISLAND}>`;
    })
    .join("\n");
}

export interface IslandHarness {
  /** The container element holding all islands */
  container: HTMLElement;
  /** All island elements found in the container */
  islands: HTMLElement[];
  /** Cleanup — removes container from DOM */
  cleanup: () => void;
}

/**
 * Creates a test harness from raw island HTML.
 *
 * Parses the HTML into real DOM elements attached to `document.body` so that
 * `querySelectorAll`, `getAttribute`, etc. work correctly.
 *
 * @example
 * ```ts
 * const harness = createIslandHarness(buildIslandHTML([
 *   { reactive: true, code: 'x = 1', output: '<div>1</div>' },
 *   { reactive: false, output: '<div>static</div>' },
 * ]));
 * // ... assertions ...
 * harness.cleanup();
 * ```
 */
export function createIslandHarness(html: string): IslandHarness {
  const container = document.createElement("div");
  container.innerHTML = html;
  document.body.appendChild(container);

  // eslint-disable-next-line unicorn/prefer-spread
  const islands = Array.from(
    container.querySelectorAll<HTMLElement>(ISLAND_TAG_NAMES.ISLAND),
  );

  return {
    container,
    islands,
    cleanup: () => container.remove(),
  };
}

// ============================================================================
// Mock Worker Factory
// ============================================================================

/**
 * Mock worker factory for testing
 */
export class MockWorkerFactory implements WorkerFactory {
  public workers: Worker[] = [];
  private readonly mockWorker?: Worker;

  constructor(mockWorker?: Worker) {
    this.mockWorker = mockWorker;
  }

  create(): Worker {
    const worker = this.mockWorker || this.createMockWorker();
    this.workers.push(worker);
    return worker;
  }

  private createMockWorker(): Worker {
    return {
      postMessage: () => {},
      terminate: () => {},
      addEventListener: () => {},
      removeEventListener: () => {},
      dispatchEvent: () => true,
      onmessage: null,
      onerror: null,
      onmessageerror: null,
    } as unknown as Worker;
  }

  getCreatedWorkers(): Worker[] {
    return this.workers;
  }

  terminateAll(): void {
    for (const worker of this.workers) {
      worker.terminate();
    }
    this.workers = [];
  }
}
