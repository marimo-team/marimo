/* Copyright 2024 Marimo. All rights reserved. */

import React from "react";

interface LazyComponentWithPreload<T> {
  preload: () => void;
  Component: React.LazyExoticComponent<React.ComponentType<T>>;
}

export const reactLazyWithPreload = <T>(
  factory: () => Promise<{ default: React.ComponentType<T> }>,
): LazyComponentWithPreload<T> => {
  let component: React.ComponentType<T> | null = null;
  const init = factory().then((module) => {
    component = module.default;
  });

  const preload = () => {
    init.then(() => {
      if (!component) {
        throw new Error("Component is not loaded");
      }
    });
  };

  const LazyComponent = React.lazy(() => {
    return init.then(() => {
      if (!component) {
        throw new Error("Component is not loaded");
      }
      return { default: component };
    });
  });

  return {
    preload,
    Component: LazyComponent,
  };
};
