/* Copyright 2026 Marimo. All rights reserved. */

import { render, screen } from "@testing-library/react";
import { Suspense } from "react";
import { expect, it, vi } from "vitest";
import { reactLazyWithPreload } from "../lazy";

it("reuses a successful preload when rendering", async () => {
  const module = { default: () => <div>Loaded</div> };
  const factory = vi.fn().mockResolvedValue(module);
  const lazy = reactLazyWithPreload(factory);

  await Promise.all([lazy.preload(), lazy.preload()]);
  render(
    <Suspense fallback="Loading">
      <lazy.Component />
    </Suspense>,
  );

  expect(await screen.findByText("Loaded")).toBeVisible();
  expect(factory).toHaveBeenCalledOnce();
});

it("retries a failed speculative preload when rendering", async () => {
  const error = new Error("Chunk download failed");
  const factory = vi
    .fn()
    .mockRejectedValueOnce(error)
    .mockResolvedValue({ default: () => <div>Loaded after retry</div> });
  const lazy = reactLazyWithPreload(factory);

  await expect(lazy.preload()).rejects.toBe(error);
  render(
    <Suspense fallback="Loading">
      <lazy.Component />
    </Suspense>,
  );

  expect(await screen.findByText("Loaded after retry")).toBeVisible();
  await lazy.preload();
  expect(factory).toHaveBeenCalledTimes(2);
});
