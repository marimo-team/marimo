/* Copyright 2026 Marimo. All rights reserved. */

import type { PyodideInterface } from "pyodide";
import { describe, expect, it, vi } from "vitest";
import { ReadonlyWasmController } from "../controller";

class TestController extends ReadonlyWasmController {
  setPyodide(pyodide: PyodideInterface) {
    this.pyodide = pyodide;
  }
}

function createPyodideStub() {
  const init = Object.assign(vi.fn(), { destroy: vi.fn() });
  const stop = Object.assign(vi.fn().mockResolvedValue(undefined), {
    destroy: vi.fn(),
  });
  const packages = { destroy: vi.fn(), toJs: () => [] };
  const sessionResources = Object.assign([{}, init, packages, stop], {
    destroy: vi.fn(),
  });
  const loadPackagesFromImports = vi.fn().mockResolvedValue(undefined);
  const pyodide = {
    runPython: vi.fn(() => sessionResources),
    loadPackagesFromImports,
    loadedPackages: {},
    runPythonAsync: vi.fn(),
  } as unknown as PyodideInterface;

  return {
    init,
    loadPackagesFromImports,
    packages,
    pyodide,
    sessionResources,
    stop,
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
});
