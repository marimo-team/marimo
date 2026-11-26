/* Copyright 2026 Marimo. All rights reserved. */

import React from "react";

interface LazyComponentWithPreload<T> {
  /**
   * Eagerly trigger the dynamic import. Returns the import promise so callers
   * can await it or attach error handling; safe to call multiple times (the
   * import is memoized).
   */
  preload: () => Promise<{ default: React.ComponentType<T> }>;
  readonly loadedComponent: React.ComponentType<T> | undefined;
  Component: React.LazyExoticComponent<React.ComponentType<T>>;
}

export const reactLazyWithPreload = <T>(
  factory: () => Promise<{ default: React.ComponentType<T> }>,
): LazyComponentWithPreload<T> => {
  let component: Promise<{ default: React.ComponentType<T> }> | null = null;
  let loadedComponent: React.ComponentType<T> | undefined;

  const preload = () => {
    if (!component) {
      component = factory().then((module) => {
        loadedComponent = module.default;
        return module;
      });
      // Fire-and-forget preloads must not surface as unhandled rejections;
      // rendering the component reports the failure through an error boundary.
      component.catch(() => undefined);
    }
    return component;
  };

  return {
    preload,
    get loadedComponent() {
      return loadedComponent;
    },
    Component: React.lazy(preload),
  };
};
