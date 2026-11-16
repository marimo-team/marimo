/* Copyright 2026 Marimo. All rights reserved. */
import type { PyodideInterface } from "pyodide";
import { afterEach, expect, it, vi } from "vitest";
import { WasmFileSystem } from "../worker/fs";

afterEach(() => vi.unstubAllGlobals());

it.each(["https://notebook.example", "null"])(
  "mounts persistent storage only for a non-opaque origin: %s",
  (origin) => {
    vi.stubGlobal("origin", origin);
    const mount = vi.fn();
    const IDBFS = {};
    const pyodide = {
      FS: { mount, filesystems: { IDBFS } },
    } as unknown as PyodideInterface;
    WasmFileSystem.mountFS(pyodide);
    expect(mount.mock.calls).toEqual(
      origin === "null" ? [] : [[IDBFS, { root: "." }, "/marimo"]],
    );
  },
);
