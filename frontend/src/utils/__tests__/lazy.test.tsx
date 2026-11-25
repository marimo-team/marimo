/* Copyright 2026 Marimo. All rights reserved. */

import { render, screen } from "@testing-library/react";
import { Suspense } from "react";
import { expect, it, vi } from "vitest";
import { Deferred } from "../Deferred";
import { reactLazyWithPreload } from "../lazy";

it("shares the loaded component between preloading and lazy rendering", async () => {
  const Page = ({ name }: { name: string }) => <div>{name}</div>;
  const module = { default: Page };
  const deferred = new Deferred<typeof module>();
  const factory = vi.fn(() => deferred.promise);
  const lazy = reactLazyWithPreload(factory);

  expect(lazy.loadedComponent).toBeUndefined();
  const first = lazy.preload();
  const second = lazy.preload();
  expect(lazy.loadedComponent).toBeUndefined();
  expect(factory).toHaveBeenCalledExactlyOnceWith();

  deferred.resolve(module);
  expect(await first).toBe(module);
  expect(await second).toBe(module);
  expect(lazy.loadedComponent).toBe(Page);

  render(
    <Suspense fallback="Loading">
      <lazy.Component name="Loaded page" />
    </Suspense>,
  );
  expect(await screen.findByText("Loaded page")).toBeVisible();
  expect(factory).toHaveBeenCalledExactlyOnceWith();
});
