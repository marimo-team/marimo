/* Copyright 2026 Marimo. All rights reserved. */
import { act, renderHook, waitFor } from "@testing-library/react";
import { Provider } from "jotai";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { MockRequestClient } from "@/__mocks__/requests";
import {
  emptyEnvironmentState,
  type EnvironmentOperation,
} from "@/core/alerts/environment";
import { alertAtom } from "@/core/alerts/state";
import { kernelStartupErrorAtom } from "@/core/errors/state";
import { connectionAtom } from "@/core/network/connection";
import { requestClientAtom } from "@/core/network/requests";
import type {
  SandboxResponse,
  SyncSandboxResponse,
} from "@/core/network/types";
import { filenameAtom } from "@/core/saving/file-state";
import { store } from "@/core/state/jotai";
import { WebSocketState } from "@/core/websocket/types";
import { HTTPError } from "@/utils/errors";
import { packageDataVersionAtom } from "../package-data";
import {
  sandboxActionsAtom,
  sandboxAtom,
  sandboxSyncAtom,
} from "../sandbox-state";
import { useSandboxController } from "../useSandboxController";

vi.mock("../toast-components", () => ({
  showPackageRestartToast: vi.fn(),
  showSandboxSyncToast: vi.fn(),
}));

const manifest = 'dependencies = ["numpy"]';
const sandbox: SandboxResponse = {
  backend: "uv",
  manifest,
  filename: "notebook.py",
};

beforeEach(() => {
  store.set(alertAtom, (value) => ({
    ...value,
    environments: {
      kernel: emptyEnvironmentState(),
      server: emptyEnvironmentState(),
    },
  }));
  store.set(sandboxAtom, null);
  store.set(sandboxSyncAtom, { pending: false, error: null });
  store.set(sandboxActionsAtom, null);
  store.set(connectionAtom, { state: WebSocketState.OPEN });
  store.set(kernelStartupErrorAtom, null);
  store.set(filenameAtom, "notebook.py");
  store.set(packageDataVersionAtom, 0);
});

function setup() {
  const client = MockRequestClient.create({
    getSandbox: vi.fn().mockResolvedValue(sandbox),
    updateManifest: vi.fn(async ({ contents }) => ({
      ...sandbox,
      manifest: contents,
    })),
    syncSandbox: vi.fn().mockResolvedValue({ success: true, reconnect: false }),
  });
  store.set(requestClientAtom, client);
  const reconnect = vi.fn<() => Promise<void>>().mockResolvedValue(undefined);
  return {
    client,
    reconnect,
    ...renderHook(() => useSandboxController(reconnect), {
      wrapper: ({ children }) => <Provider store={store}>{children}</Provider>,
    }),
  };
}

describe("useSandboxController", () => {
  it("restores sync progress and lets a retry replace the restored failure", async () => {
    const operation: EnvironmentOperation = {
      operation_id: "sync",
      action: "sync",
      source: "kernel",
      status: { kind: "running" },
      packages: {},
      logs: {},
    };
    const restore = (status: EnvironmentOperation["status"]) =>
      store.set(alertAtom, (value) => ({
        ...value,
        environments: {
          ...value.environments,
          kernel: {
            restart_required: false,
            operations: [{ ...operation, status }],
          },
        },
      }));
    restore({ kind: "running" });
    const { client, result } = setup();
    const actions = store.get(sandboxActionsAtom)!;
    expect(result.current.pending).toBe(true);
    await act(async () => {
      expect(await actions.sync()).toBe(false);
    });
    expect(client.syncSandbox).not.toHaveBeenCalled();
    act(() => restore({ kind: "failed", error: "Dependency conflict" }));
    expect(result.current.diagnostic).toBe("Dependency conflict");

    const { promise, resolve } = Promise.withResolvers<SyncSandboxResponse>();
    vi.mocked(client.syncSandbox).mockReturnValue(promise);
    let pending: Promise<boolean>;
    act(() => {
      pending = actions.sync();
    });
    expect(store.get(sandboxSyncAtom)).toEqual({ pending: true, error: null });
    act(() => restore({ kind: "running" }));
    await act(async () => {
      resolve({ success: true, reconnect: false });
      expect(await pending).toBe(true);
    });
    // The response can arrive before the final websocket notification.
    expect(store.get(sandboxSyncAtom)).toEqual({ pending: true, error: null });
    act(() => restore({ kind: "succeeded" }));
    expect(store.get(sandboxSyncAtom)).toEqual({ pending: false, error: null });
  });

  it("keeps a conflicting draft across closing and only discards it on explicit reload", async () => {
    const { result, client } = setup();
    vi.mocked(client.updateManifest).mockRejectedValue(
      new HTTPError(409, "Conflict", { detail: "Manifest changed on disk" }),
    );
    await act(async () => {
      await store.get(sandboxActionsAtom)?.editManifest();
    });
    act(() => result.current.setDraft("dependencies = []"));
    await act(async () => {
      await result.current.saveAndSync();
    });
    expect(client.updateManifest).toHaveBeenCalledExactlyOnceWith({
      fileKey: "notebook.py",
      previous: manifest,
      contents: "dependencies = []",
    });
    expect(result.current).toMatchObject({
      open: true,
      draft: "dependencies = []",
      dirty: true,
      conflict: true,
      diagnostic: "Manifest changed on disk",
      pending: false,
    });
    expect(client.syncSandbox).not.toHaveBeenCalled();
    act(() => result.current.setOpen(false));
    await act(async () => {
      await store.get(sandboxActionsAtom)?.editManifest();
    });
    expect(result.current.draft).toBe("dependencies = []");
    await act(async () => {
      await result.current.loadManifest();
    });
    expect(result.current).toMatchObject({
      draft: manifest,
      dirty: false,
      conflict: false,
      diagnostic: null,
    });
  });

  it("shares sync progress across callers and refreshes packages without reconnecting", async () => {
    const { client, reconnect } = setup();
    const { promise, resolve } = Promise.withResolvers<SyncSandboxResponse>();
    vi.mocked(client.syncSandbox).mockReturnValue(promise);
    const actions = store.get(sandboxActionsAtom)!;
    let pending: Promise<boolean>;
    act(() => {
      pending = actions.sync();
    });
    expect(store.get(sandboxSyncAtom)).toEqual({ pending: true, error: null });
    await act(async () => {
      expect(await actions.sync()).toBe(false);
    });
    expect(client.syncSandbox).toHaveBeenCalledTimes(1);
    await act(async () => {
      resolve({ success: true, reconnect: false });
      expect(await pending).toBe(true);
    });
    expect(store.get(sandboxSyncAtom)).toEqual({ pending: false, error: null });
    expect(store.get(packageDataVersionAtom)).toBe(1);
    expect(reconnect).not.toHaveBeenCalled();
  });

  it("reports sync failure and clears it when retrying", async () => {
    const { client } = setup();
    const actions = store.get(sandboxActionsAtom)!;
    vi.mocked(client.syncSandbox).mockRejectedValueOnce(new Error("offline"));
    await act(async () => {
      expect(await actions.sync()).toBe(false);
    });
    expect(store.get(sandboxSyncAtom)).toEqual({
      pending: false,
      error: "offline",
    });
    await act(async () => {
      expect(await actions.sync()).toBe(true);
    });
    expect(store.get(sandboxSyncAtom)).toEqual({ pending: false, error: null });
  });

  it("ignores stale metadata after a filename change and unregisters actions on unmount", async () => {
    const { client, unmount } = setup();
    await waitFor(() => expect(store.get(sandboxAtom)).toEqual(sandbox));
    const { promise, resolve } = Promise.withResolvers<SandboxResponse>();
    vi.mocked(client.getSandbox).mockReturnValueOnce(promise);
    act(() => store.set(filenameAtom, "old.py"));
    const current = { ...sandbox, filename: "current.py" };
    vi.mocked(client.getSandbox).mockResolvedValue(current);
    act(() => store.set(filenameAtom, "current.py"));
    await waitFor(() => expect(store.get(sandboxAtom)).toEqual(current));
    await act(async () => resolve({ ...sandbox, filename: "old.py" }));
    expect(store.get(sandboxAtom)).toEqual(current);
    unmount();
    expect(store.get(sandboxActionsAtom)).toBeNull();
  });
});
