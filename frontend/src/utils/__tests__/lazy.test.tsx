/* Copyright 2026 Marimo. All rights reserved. */

import { render, screen } from "@testing-library/react";
import { Suspense } from "react";
import { expect, it, vi } from "vitest";
import { Deferred } from "../Deferred";
import { reactLazyWithPreload } from "../lazy";

it("shares one import between preloading and both components", async () => {
  const Page = ({ name }: { name: string }) => <div>{name}</div>;
  const module = { default: Page };
  const deferred = new Deferred<typeof module>();
  const factory = vi.fn(() => deferred.promise);
  const lazy = reactLazyWithPreload(factory);

  const first = lazy.preload();
  const second = lazy.preload();
  expect(first).toBe(second);

  deferred.resolve(module);
  expect(await first).toBe(module);

  render(<lazy.NonSuspendingComponent name="Eager page" />);
  expect(screen.getByText("Eager page")).toBeVisible();

  render(
    <Suspense fallback="Loading">
      <lazy.Component name="Lazy page" />
    </Suspense>,
  );
  expect(await screen.findByText("Lazy page")).toBeVisible();
  expect(factory).toHaveBeenCalledExactlyOnceWith();
});
