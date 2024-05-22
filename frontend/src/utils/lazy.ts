/* Copyright 2024 Marimo. All rights reserved. */

import React from "react";

interface LazyComponentWithPreload<T> {
  preload: () => void;
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
