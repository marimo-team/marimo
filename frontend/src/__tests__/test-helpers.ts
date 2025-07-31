/* Copyright 2024 Marimo. All rights reserved. */

/**
 * Common test patterns
 */
export const TestUtils = {
  /**
   * Create a promise that resolves after a tick
   */
  nextTick: () => new Promise((resolve) => setTimeout(resolve, 0)),

  /**
   * Wait for a specific condition to be true
   */
  waitFor: async (condition: () => boolean, timeout = 1000) => {
    const start = Date.now();
    while (!condition() && Date.now() - start < timeout) {
      await TestUtils.nextTick();
    }
    if (!condition()) {
      throw new Error(`Condition not met within ${timeout}ms`);
    }
  },
};
