/* Copyright 2026 Marimo. All rights reserved. */

import React, { useEffect, useState } from "react";

interface LazyComponentWithPreload<T> {
  /**
   * Eagerly trigger the dynamic import. Returns the import promise so callers
   * can await it or attach error handling; safe to call multiple times (the
   * import is memoized).
   */
  preload: () => Promise<{ default: React.ComponentType<T> }>;
  Component: React.LazyExoticComponent<React.ComponentType<T>>;
  /**
   * Like `Component`, but loads through state instead of suspending, which
   * avoids React's throttled retry of a suspended boundary. Renders nothing
   * while loading and throws import failures to the nearest error boundary.
   */
  NonSuspendingComponent: React.FC<T & React.JSX.IntrinsicAttributes>;
}

type LoadResult<T> = { component: React.ComponentType<T> } | { error: unknown };

export const reactLazyWithPreload = <T,>(
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

  const NonSuspendingComponent = (props: T & React.JSX.IntrinsicAttributes) => {
    // The compiler outlines closures over factory-scoped variables to module
    // scope, where `loadedComponent` is undefined.
    "use no memo";
    const [result, setResult] = useState<LoadResult<T> | undefined>(() =>
      loadedComponent ? { component: loadedComponent } : undefined,
    );

    useEffect(() => {
      if (result) {
        return;
      }
      preload().then(
        (module) => setResult({ component: module.default }),
        (error: unknown) => setResult({ error }),
      );
    }, [result]);

    if (!result) {
      return null;
    }
    if ("error" in result) {
      throw result.error;
    }
    return <result.component {...props} />;
  };

  return {
    preload,
    Component: React.lazy(preload),
    NonSuspendingComponent,
  };
};
