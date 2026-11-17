/* Copyright 2026 Marimo. All rights reserved. */

import type { PyodideInterface } from "pyodide";
import { describe, expect, it, vi } from "vitest";
import { Deferred } from "@/utils/Deferred";
import { ReadonlyWasmController } from "../controller";

class TestController extends ReadonlyWasmController {
  public setPyodide(pyodide: PyodideInterface) {
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

function prepareSession(controller: TestController, code: string) {
  return controller.prepareSession({
    code,
    filename: `${code}.py`,
  });
}

async function startSession(controller: TestController, code: string) {
  const session = await prepareSession(controller, code);
  void session.start();
  return session;
}

describe("WASM controller session lifecycle", () => {
  it("releases a prepared session and ignores start after stop", async () => {
    const { init, pyodide } = createPyodideStub();
    const controller = new TestController();
    controller.setPyodide(pyodide);

    const session = await prepareSession(controller, "current");
    await session.stop();
    expect(init.destroy).toHaveBeenCalledOnce();
    await session.start();
    expect(init).not.toHaveBeenCalled();
  });

  it.each(["resolve", "reject"] as const)(
    "releases a stopped session before its dependencies %s",
    async (outcome) => {
      const dependencies = new Deferred<void>();
      const { init, loadPackagesFromImports, pyodide, bridge, stop } =
        createPyodideStub();
      loadPackagesFromImports.mockReturnValue(dependencies.promise);
      const controller = new TestController();
      controller.setPyodide(pyodide);
      const session = await prepareSession(controller, "current");
      const starting = session.start();
      expect(init).not.toHaveBeenCalled();
      await session.stop();
      expect(init.destroy).toHaveBeenCalledOnce();
      expect(bridge.destroy).toHaveBeenCalledOnce();
      if (outcome === "resolve") {
        dependencies.resolve();
      } else {
        dependencies.reject(new Error("Loading failed after stop"));
      }
      await starting;
      await session.stop();
      expect(stop).toHaveBeenCalledOnce();
      expect(init).not.toHaveBeenCalled();
    },
  );

  it("reports dependency failures when starting an active session", async () => {
    const { init, loadPackagesFromImports, pyodide } = createPyodideStub();
    loadPackagesFromImports.mockRejectedValue(new Error("Dependency failed"));
    const controller = new TestController();
    controller.setPyodide(pyodide);
    const session = await prepareSession(controller, "current");
    await expect(session.start()).rejects.toThrow("Dependency failed");
    expect(init).not.toHaveBeenCalled();
    expect(init.destroy).toHaveBeenCalledOnce();
    await session.stop();
  });

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

    expect(first.stop.destroy).not.toHaveBeenCalled();

    await controller.stopSession();

    expect(first.stop).toHaveBeenCalledOnce();
    expect(second.stop).toHaveBeenCalledOnce();
    expect(first.stop.destroy).toHaveBeenCalledOnce();
    expect(second.stop.destroy).toHaveBeenCalledOnce();
    expect(first.bridge.destroy).toHaveBeenCalledOnce();
    expect(second.bridge.destroy).toHaveBeenCalledOnce();
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

  it("reports and retries a falsy stop failure", async () => {
    const session = createSessionResources(() => Promise.reject(false));
    const { pyodide } = createPyodideStub([session]);
    const controller = new TestController();
    controller.setPyodide(pyodide);

    await startSession(controller, "current");

    await expect(controller.stopSession()).rejects.toBe(false);
    expect(session.stop.destroy).not.toHaveBeenCalled();

    session.stop.mockResolvedValueOnce(undefined);
    await controller.stopSession();

    expect(session.stop).toHaveBeenCalledTimes(2);
    expect(session.stop.destroy).toHaveBeenCalledOnce();
  });
});
