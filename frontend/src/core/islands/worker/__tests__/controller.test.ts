/* Copyright 2026 Marimo. All rights reserved. */

import type { PyodideInterface } from "pyodide";
import { describe, expect, it, vi } from "vitest";
import { ReadonlyWasmController } from "../controller";

class TestController extends ReadonlyWasmController {
  setPyodide(pyodide: PyodideInterface) {
    this.pyodide = pyodide;
  }
}

function createSessionResources(
  stopImplementation: () => Promise<void> = () => Promise.resolve(),
) {
  const bridge = { destroy: vi.fn() };
  const init = Object.assign(vi.fn(), { destroy: vi.fn() });
  const stop = Object.assign(vi.fn(stopImplementation), {
    destroy: vi.fn(),
  });
  const packages = { destroy: vi.fn(), toJs: () => [] };
  const sessionResources = Object.assign([bridge, init, packages, stop], {
    destroy: vi.fn(),
  });

  return { bridge, init, packages, sessionResources, stop };
}

function createPyodideStub(
  sessions = Array.from({ length: 4 }, () => createSessionResources()),
) {
  const [first] = sessions;
  if (!first) {
    throw new Error("At least one session is required");
  }
  const loadPackagesFromImports = vi.fn().mockResolvedValue(undefined);
  const pyodide = {
    runPython: vi
      .fn()
      .mockImplementation(() => sessions.shift()?.sessionResources),
    loadPackagesFromImports,
    loadedPackages: {},
    runPythonAsync: vi.fn(),
  } as unknown as PyodideInterface;

  return {
    ...first,
    loadPackagesFromImports,
    pyodide,
  };
}

function startSession(controller: TestController, code: string) {
  return controller.startSession({
    code,
    filename: `${code}.py`,
    onMessage: vi.fn(),
  });
}

describe("WASM controller session lifecycle", () => {
  it("stops and releases the active session", async () => {
    const { init, packages, pyodide, sessionResources, stop } =
      createPyodideStub();
    const controller = new TestController();
    controller.setPyodide(pyodide);

    await startSession(controller, "current");
    await vi.waitFor(() => expect(init).toHaveBeenCalledOnce());
    await controller.stopSession();

    expect(stop).toHaveBeenCalledOnce();
    expect(stop.destroy).toHaveBeenCalledOnce();
    expect(sessionResources.destroy).toHaveBeenCalledOnce();
    expect(packages.destroy).toHaveBeenCalledOnce();
    expect(init.destroy).toHaveBeenCalledOnce();
  });

  it("loads dependencies serially and skips superseded sessions", async () => {
    let finishFirstLoad!: () => void;
    const { loadPackagesFromImports, pyodide } = createPyodideStub();
    loadPackagesFromImports
      .mockReturnValueOnce(
        new Promise<void>((resolve) => {
          finishFirstLoad = resolve;
        }),
      )
      .mockResolvedValueOnce(undefined);
    const controller = new TestController();
    controller.setPyodide(pyodide);

    await startSession(controller, "first_dependency");
    await startSession(controller, "superseded_dependency");
    await controller.stopSession();
    await startSession(controller, "current_dependency");

    expect(loadPackagesFromImports).toHaveBeenCalledOnce();
    finishFirstLoad();
    await vi.waitFor(() =>
      expect(loadPackagesFromImports).toHaveBeenCalledTimes(2),
    );

    const loadedSources = loadPackagesFromImports.mock.calls.map(
      ([source]) => source as string,
    );
    expect(loadedSources[1]).toContain("current_dependency");
    expect(loadedSources.join("\n")).not.toContain("superseded_dependency");
  });

  it("stops every session created for a multi-app page", async () => {
    const first = createSessionResources();
    const second = createSessionResources();
    const { pyodide } = createPyodideStub([first, second]);
    const controller = new TestController();
    controller.setPyodide(pyodide);

    await startSession(controller, "first");
    await startSession(controller, "second");
    second.bridge.destroy();

    expect(first.stop.destroy).not.toHaveBeenCalled();

    await controller.stopSession();

    expect(first.stop).toHaveBeenCalledOnce();
    expect(second.stop).toHaveBeenCalledOnce();
    expect(first.stop.destroy).toHaveBeenCalledOnce();
    expect(second.stop.destroy).toHaveBeenCalledOnce();
  });

  it("continues stopping sessions after one stop fails", async () => {
    const failure = new Error("stop failed");
    const first = createSessionResources(() => Promise.reject(failure));
    const second = createSessionResources();
    const { pyodide } = createPyodideStub([first, second]);
    const controller = new TestController();
    controller.setPyodide(pyodide);

    await startSession(controller, "first");
    await startSession(controller, "second");

    await expect(controller.stopSession()).rejects.toThrow("stop failed");
    expect(first.stop).toHaveBeenCalledOnce();
    expect(second.stop).toHaveBeenCalledOnce();
    expect(first.stop.destroy).not.toHaveBeenCalled();
    expect(second.stop.destroy).toHaveBeenCalledOnce();

    first.stop.mockResolvedValueOnce(undefined);
    await controller.stopSession();

    expect(first.stop).toHaveBeenCalledTimes(2);
    expect(first.stop.destroy).toHaveBeenCalledOnce();
    expect(second.stop).toHaveBeenCalledOnce();
  });
});
