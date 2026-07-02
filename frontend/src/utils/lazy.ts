/* Copyright 2026 Marimo. All rights reserved. */

import React from "react";

interface LazyComponentWithPreload<T> {
  /**
   * Eagerly trigger the dynamic import. Returns the import promise so callers
   * can await it or attach error handling; safe to call multiple times (the
   * import is memoized).
   */
  preload: () => Promise<{ default: React.ComponentType<T> }>;
  Component: React.LazyExoticComponent<React.ComponentType<T>>;
}

export const reactLazyWithPreload = <T>(
  factory: () => Promise<{ default: React.ComponentType<T> }>,
): LazyComponentWithPreload<T> => {
  let component: Promise<{ default: React.ComponentType<T> }> | null = null;

  const preload = async () => {
    if (!component) {
      component = factory();
    }
    return component;
  };

  const LazyComponent = React.lazy(() => {
    return preload();
  });

  return {
    preload,
    Component: LazyComponent,
  };
};
