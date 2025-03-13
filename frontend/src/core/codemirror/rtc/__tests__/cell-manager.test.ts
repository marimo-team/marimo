/* Copyright 2024 Marimo. All rights reserved. */
import {
  describe,
  it,
  expect,
  vi,
  beforeEach,
  afterEach,
  type Mock,
} from "vitest";
import { CellProviderManager } from "../cell-manager";
import { WebsocketProvider } from "y-websocket";
import * as Y from "yjs";
import { store } from "@/core/state/jotai";
import { WebSocketState } from "@/core/websocket/types";
import { getSessionId } from "@/core/kernel/session";
import type { CellId } from "@/core/cells/ids";
import { connectionAtom } from "@/core/network/connection";

// Mock dependencies
vi.mock("y-websocket", () => ({
  WebsocketProvider: vi.fn().mockImplementation(() => ({
    on: vi.fn(),
    destroy: vi.fn(),
  })),
}));

vi.mock("@/core/kernel/session", () => ({
  getSessionId: vi.fn(),
}));

const CELL_ID = "cell1" as CellId;

describe("CellProviderManager", () => {
  let manager: CellProviderManager;
  const mockProvider = {
    doc: {
      getText: vi.fn(),
    },
    on: vi.fn(),
    destroy: vi.fn(),
  };
  const mockYText = {};

  beforeEach(() => {
    vi.clearAllMocks();
    manager = CellProviderManager.getInstance();
    (WebsocketProvider as Mock).mockImplementation(() => mockProvider);
    mockProvider.doc.getText.mockReturnValue(mockYText);
    store.set(connectionAtom, { state: WebSocketState.OPEN });
    vi.spyOn(store, "get");
    (getSessionId as Mock).mockReturnValue("test-session");
  });

  afterEach(() => {
    manager.disconnectAll();
  });

  it("should be a singleton", () => {
    const instance1 = CellProviderManager.getInstance();
    const instance2 = CellProviderManager.getInstance();
    expect(instance1).toBe(instance2);
  });

  it("should create new provider if none exists", async () => {
    const { provider, ytext } = manager.getOrCreateProvider(
      CELL_ID,
      "initial code",
    );

    expect(WebsocketProvider).toHaveBeenCalledWith(
      "ws",
      CELL_ID,
      expect.any(Y.Doc),
      {
        params: {
          session_id: "test-session",
        },
        resyncInterval: 5000,
      },
    );
    expect(provider).toBe(mockProvider);
    expect(ytext.toJSON()).toBe("initial code");
  });

  it("should return existing provider if one exists", async () => {
    manager.getOrCreateProvider(CELL_ID, "initial code");
    const { provider: provider2 } = manager.getOrCreateProvider(
      CELL_ID,
      "different code",
    );

    expect(WebsocketProvider).toHaveBeenCalledTimes(1);
    expect(provider2).toBe(mockProvider);
  });

  it("should include file path in params if present", async () => {
    const originalLocation = window.location;
    // @ts-expect-error ehhh typescript
    // biome-ignore lint/performance/noDelete: ehh
    delete window.location;
    window.location = {
      ...originalLocation,
      search: "?file=/path/to/file.py",
    };

    manager.getOrCreateProvider(CELL_ID, "initial code");

    expect(WebsocketProvider).toHaveBeenCalledWith(
      "ws",
      "cell1",
      expect.any(Y.Doc),
      {
        params: {
          session_id: "test-session",
          file: "/path/to/file.py",
        },
        resyncInterval: 5000,
      },
    );
  });

  it("should disconnect a specific provider", () => {
    manager.getOrCreateProvider(CELL_ID, "code");
    manager.disconnect(CELL_ID);

    expect(mockProvider.destroy).toHaveBeenCalled();
  });

  it("should disconnect all providers", async () => {
    manager.getOrCreateProvider(CELL_ID, "code");
    manager.getOrCreateProvider("cell2" as CellId, "code");
    manager.disconnectAll();

    expect(mockProvider.destroy).toHaveBeenCalledTimes(2);
  });
});
