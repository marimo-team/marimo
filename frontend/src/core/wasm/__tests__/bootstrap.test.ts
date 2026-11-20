/* Copyright 2026 Marimo. All rights reserved. */

import { loadPyodide } from "pyodide";
import type { PyodideInterface } from "pyodide";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { DefaultWasmController, requirementName } from "../worker/bootstrap";

vi.mock("pyodide", () => ({ loadPyodide: vi.fn() }));
vi.mock("../worker/getMarimoWheel", () => ({
  getMarimoWheel: () => "marimo-base",
}));

const micropip = { set_index_urls: vi.fn(), destroy: vi.fn() };
const pyodide = { pyimport: vi.fn(() => micropip) };

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(loadPyodide).mockResolvedValue(
    pyodide as unknown as PyodideInterface,
  );
});

describe("WASM runtime sources", () => {
  it("preserves the default runtime sources", async () => {
    await new DefaultWasmController().bootstrap({
      version: "0.24.2",
      pyodideVersion: "v314.0.0",
    });
    expect(loadPyodide).toHaveBeenCalledWith(
      expect.objectContaining({
        indexURL: "https://cdn.jsdelivr.net/pyodide/v314.0.0/full/",
        packageBaseUrl: "https://cdn.jsdelivr.net/pyodide/v314.0.0/full/",
        lockFileURL:
          "https://wasm.marimo.app/pyodide-lock.json?v=0.24.2&pyodide=v314.0.0",
      }),
    );
    expect(pyodide.pyimport).not.toHaveBeenCalled();
  });

  it("configures runtime and package sources before returning the interpreter", async () => {
    const controller = new DefaultWasmController();
    await controller.bootstrap({
      version: "0.24.2",
      pyodideVersion: "v314.0.0",
      pyodideIndexUrl: "https://example.com/runtime/",
      pyodideLockfileUrl: "https://example.com/lock.json",
      pypiIndexUrl: "https://example.com/pypi/{package_name}/json",
    });
    expect(loadPyodide).toHaveBeenCalledWith(
      expect.objectContaining({
        indexURL: "https://example.com/runtime/",
        packageBaseUrl: "https://example.com/runtime/",
        lockFileURL: "https://example.com/lock.json",
      }),
    );
    expect(pyodide.pyimport).toHaveBeenCalledWith("micropip");
    expect(micropip.set_index_urls).toHaveBeenCalledWith(
      "https://example.com/pypi/{package_name}/json",
    );
    expect(micropip.destroy).toHaveBeenCalledOnce();
    expect(controller.requirePyodide).toBe(pyodide);
  });
});

describe("requirementName", () => {
  it("returns the distribution name for a bare requirement", () => {
    expect(requirementName("pandas")).toBe("pandas");
  });

  it.each([
    ["pandas==2.1.0", "pandas"],
    ["pandas>=2", "pandas"],
    ["pandas<=2", "pandas"],
    ["pandas~=2.1", "pandas"],
    ["pandas!=2.0", "pandas"],
    ["nltools===0.6.0.dev2", "nltools"],
  ])("cuts the specifier off %s", (requirement, expected) => {
    expect(requirementName(requirement)).toBe(expected);
  });

  it("cuts extras and markers", () => {
    expect(requirementName("rich[jupyter]>=13")).toBe("rich");
    expect(requirementName('cowsay==6.1; sys_platform == "emscripten"')).toBe(
      "cowsay",
    );
  });

  it("cuts a URL requirement at the name", () => {
    expect(requirementName("pkg @ https://example.com/pkg.whl")).toBe("pkg");
  });

  it("tolerates surrounding whitespace", () => {
    expect(requirementName("  pandas >= 2  ")).toBe("pandas");
  });
});
