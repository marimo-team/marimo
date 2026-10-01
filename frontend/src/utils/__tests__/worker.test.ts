/* Copyright 2026 Marimo. All rights reserved. */
import { afterEach, describe, expect, it, vi } from "vitest";
import { createModuleWorker } from "../worker";

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("createModuleWorker", () => {
  it.each(["http", "blob"])(
    "preserves caller-owned %s worker URLs",
    (scheme) => {
      const Worker = vi.fn(function (
        _url: string | URL,
        _options: WorkerOptions,
      ) {
        return {};
      });
      vi.stubGlobal("Worker", Worker);
      const url = new URL(
        scheme === "blob"
          ? `blob:${location.origin}/worker`
          : new URL("/worker.js", location.href),
      );
      const revoke = vi.spyOn(URL, "revokeObjectURL");
      createModuleWorker(url, { name: "marimo" });
      expect(Worker).toHaveBeenCalledWith(url.href, {
        type: "module",
        name: "marimo",
      });
      expect(revoke).not.toHaveBeenCalled();
    },
  );

  it("preserves the page origin for hosted CDN workers", () => {
    const Worker = vi.fn(function (
      _url: string | URL,
      _options: WorkerOptions,
    ) {
      return {};
    });
    vi.stubGlobal("Worker", Worker);
    const create = vi
      .spyOn(URL, "createObjectURL")
      .mockReturnValue("blob:worker");
    const revoke = vi
      .spyOn(URL, "revokeObjectURL")
      .mockImplementation(() => undefined);
    createModuleWorker(new URL("https://cdn.example.com/worker.js"), {
      name: "islands",
    });
    expect(create).toHaveBeenCalledWith(expect.any(Blob));
    expect(Worker).toHaveBeenCalledWith("blob:worker", {
      type: "module",
      name: "islands",
    });
    expect(revoke).toHaveBeenCalledWith("blob:worker");
  });

  it("imports a CDN worker from an opaque origin", () => {
    const Worker = vi.fn(function (
      _url: string | URL,
      _options: WorkerOptions,
    ) {
      return {};
    });
    vi.stubGlobal("Worker", Worker);
    vi.stubGlobal("origin", "null");
    const url = new URL("https://cdn.example.com/worker.js");
    createModuleWorker(url, { name: "0.24.2::controller" });
    const [source, options] = Worker.mock.calls[0];
    expect(decodeURIComponent(String(source))).toBe(
      'data:application/javascript,import "https://cdn.example.com/worker.js"',
    );
    expect(options).toEqual({
      type: "module",
      name: "0.24.2::controller",
    });
  });
});
