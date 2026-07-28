/* Copyright 2026 Marimo. All rights reserved. */
import type {
  JSONRPCMessage,
  JSONRPCNotification,
  JSONRPCRequest,
  Transport,
} from "@marimo-team/codemirror-languageserver";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { store } from "@/core/state/jotai";
import { CopilotLanguageServerClient } from "../language-server";
import { copilotStatusState } from "../state";

const copilotState = vi.hoisted(() => ({ isEnabled: true }));

vi.mock("../state", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../state")>();
  return {
    ...actual,
    isCopilotEnabled: () => copilotState.isEnabled,
  };
});

class MockTransport implements Transport {
  private readonly handlers = new Set<(message: JSONRPCMessage) => void>();
  readonly sent: JSONRPCMessage[] = [];

  connect = vi.fn().mockResolvedValue(undefined);
  close = vi.fn();
  send = vi.fn((message: JSONRPCMessage) => {
    this.sent.push(message);
    if (isRequest(message) && message.method === "initialize") {
      queueMicrotask(() => {
        this.emit({
          jsonrpc: "2.0",
          id: message.id,
          result: { capabilities: {} },
        });
      });
    }
  });

  onMessage(handler: (message: JSONRPCMessage) => void): () => void {
    this.handlers.add(handler);
    return () => {
      this.handlers.delete(handler);
    };
  }

  emit(message: JSONRPCMessage) {
    for (const handler of this.handlers) {
      handler(message);
    }
  }
}

function isRequest(message: JSONRPCMessage): message is JSONRPCRequest {
  return "method" in message && "id" in message;
}

function notifications(
  transport: MockTransport,
  method: string,
): JSONRPCNotification[] {
  return transport.sent.filter(
    (message): message is JSONRPCNotification =>
      "method" in message && !("id" in message) && message.method === method,
  );
}

describe("CopilotLanguageServerClient", () => {
  let mockTransport: MockTransport;

  beforeEach(() => {
    copilotState.isEnabled = true;
    mockTransport = new MockTransport();
  });

  it("initializes without copilot settings", () => {
    const client = new CopilotLanguageServerClient({
      rootUri: "file:///test",
      workspaceFolders: null,
      transport: mockTransport,
    });

    expect(client).toBeDefined();
  });

  it("initializes with copilot settings", () => {
    const client = new CopilotLanguageServerClient({
      rootUri: "file:///test",
      workspaceFolders: null,
      transport: mockTransport,
      copilotSettings: {
        http: {
          proxy: "http://proxy.example.com:8888",
          proxyStrictSSL: true,
        },
        telemetry: {
          telemetryLevel: "off",
        },
      },
    });

    expect(client).toBeDefined();
  });

  it("sends configuration after initialization", async () => {
    const copilotSettings = {
      http: {
        proxy: "http://proxy.example.com:8888",
        proxyStrictSSL: true,
      },
    };
    const client = new CopilotLanguageServerClient({
      rootUri: "file:///test",
      workspaceFolders: null,
      transport: mockTransport,
      copilotSettings,
    });
    await client.initializePromise;
    await vi.waitFor(() => {
      expect(
        notifications(mockTransport, "workspace/didChangeConfiguration"),
      ).toEqual([
        {
          jsonrpc: "2.0",
          method: "workspace/didChangeConfiguration",
          params: { settings: copilotSettings },
        },
      ]);
    });
  });

  it.each([
    ["empty", {}],
    ["omitted", undefined],
  ])(
    "does not send configuration when settings are %s",
    async (_, copilotSettings) => {
      const client = new CopilotLanguageServerClient({
        rootUri: "file:///test",
        workspaceFolders: null,
        transport: mockTransport,
        copilotSettings,
      });
      await client.initializePromise;
      await new Promise((resolve) => setTimeout(resolve, 0));

      expect(
        notifications(mockTransport, "workspace/didChangeConfiguration"),
      ).toEqual([]);
    },
  );

  it("accepts enterprise, proxy, and telemetry settings together", async () => {
    const copilotSettings = {
      http: {
        proxy: "http://proxy.example.com:8888",
        proxyStrictSSL: true,
        proxyKerberosServicePrincipal: "HTTP/proxy.example.com",
      },
      telemetry: {
        telemetryLevel: "all",
      },
      "github-enterprise": {
        uri: "https://github.enterprise.com",
      },
    };
    const client = new CopilotLanguageServerClient({
      rootUri: "file:///test",
      workspaceFolders: null,
      transport: mockTransport,
      copilotSettings,
    });
    await client.initializePromise;
    await vi.waitFor(() => {
      expect(
        notifications(mockTransport, "workspace/didChangeConfiguration"),
      ).toEqual([
        {
          jsonrpc: "2.0",
          method: "workspace/didChangeConfiguration",
          params: { settings: copilotSettings },
        },
      ]);
    });
  });

  it("reopens the latest Copilot document after re-initialization", async () => {
    const client = new CopilotLanguageServerClient({
      rootUri: "file:///test",
      workspaceFolders: null,
      transport: mockTransport,
    });
    await client.initializePromise;
    await client.textDocumentDidOpen({
      textDocument: {
        uri: "file:///test.py",
        languageId: "python",
        version: 0,
        text: "initial",
      },
    });
    await client.textDocumentDidChange({
      textDocument: { uri: "file:///test.py", version: 1 },
      contentChanges: [{ text: "updated" }],
    });
    mockTransport.sent.length = 0;

    await client.reInitialize();

    expect(notifications(mockTransport, "textDocument/didOpen")).toEqual([
      {
        jsonrpc: "2.0",
        method: "textDocument/didOpen",
        params: {
          textDocument: {
            uri: "file:///test.py",
            languageId: "python",
            version: 1,
            text: "updated",
          },
        },
      },
    ]);
  });

  it("reopens the document with the languageId it was opened with", async () => {
    const client = new CopilotLanguageServerClient({
      rootUri: "file:///test",
      workspaceFolders: null,
      transport: mockTransport,
    });
    await client.initializePromise;
    // The Copilot plugin opens as "copilot", not "python"
    await client.textDocumentDidOpen({
      textDocument: {
        uri: "file:///test.py",
        languageId: "copilot",
        version: 0,
        text: "initial",
      },
    });
    await client.textDocumentDidChange({
      textDocument: { uri: "file:///test.py", version: 1 },
      contentChanges: [{ text: "updated" }],
    });
    mockTransport.sent.length = 0;

    await client.reInitialize();

    expect(notifications(mockTransport, "textDocument/didOpen")).toEqual([
      {
        jsonrpc: "2.0",
        method: "textDocument/didOpen",
        params: {
          textDocument: {
            uri: "file:///test.py",
            languageId: "copilot",
            version: 1,
            text: "updated",
          },
        },
      },
    ]);
  });

  it("ignores an empty didChange without corrupting document state", async () => {
    const client = new CopilotLanguageServerClient({
      rootUri: "file:///test",
      workspaceFolders: null,
      transport: mockTransport,
    });
    await client.initializePromise;
    mockTransport.sent.length = 0;

    await expect(
      client.textDocumentDidChange({
        textDocument: { uri: "file:///test.py", version: 1 },
        contentChanges: [],
      }),
    ).resolves.toBeUndefined();

    expect(notifications(mockTransport, "textDocument/didOpen")).toEqual([]);
    expect(notifications(mockTransport, "textDocument/didChange")).toEqual([]);
  });

  it("balances document references when Copilot is disabled before close", async () => {
    const client = new CopilotLanguageServerClient({
      rootUri: "file:///test",
      workspaceFolders: null,
      transport: mockTransport,
    });
    await client.initializePromise;
    await client.textDocumentDidOpen({
      textDocument: {
        uri: "file:///test.py",
        languageId: "python",
        version: 7,
        text: "value = 1",
      },
    });

    copilotState.isEnabled = false;
    await client.textDocumentDidClose({
      textDocument: { uri: "file:///test.py" },
    });
    copilotState.isEnabled = true;
    mockTransport.sent.length = 0;
    await client.reInitialize();

    expect(notifications(mockTransport, "textDocument/didOpen")).toEqual([]);
  });

  it("keeps document versions monotonic after opening a versioned document", async () => {
    const client = new CopilotLanguageServerClient({
      rootUri: "file:///test",
      workspaceFolders: null,
      transport: mockTransport,
    });
    await client.initializePromise;
    await client.textDocumentDidOpen({
      textDocument: {
        uri: "file:///test.py",
        languageId: "python",
        version: 7,
        text: "value = 1",
      },
    });
    mockTransport.sent.length = 0;

    await client.textDocumentDidChange({
      textDocument: { uri: "file:///test.py", version: 8 },
      contentChanges: [{ text: "value = 2" }],
    });

    expect(notifications(mockTransport, "textDocument/didChange")).toEqual([
      {
        jsonrpc: "2.0",
        method: "textDocument/didChange",
        params: {
          textDocument: { uri: "file:///test.py", version: 8 },
          contentChanges: [{ text: "value = 2" }],
        },
      },
    ]);
  });

  it("ignores malformed custom notifications", async () => {
    const client = new CopilotLanguageServerClient({
      rootUri: "file:///test",
      workspaceFolders: null,
      transport: mockTransport,
    });
    await client.initializePromise;

    expect(() => {
      mockTransport.emit({
        jsonrpc: "2.0",
        method: "statusNotification",
        params: { busy: "not-a-boolean" },
      });
      mockTransport.emit({
        jsonrpc: "2.0",
        method: "window/logMessage",
        params: null,
      });
    }).not.toThrow();
  });

  describe("status notifications", () => {
    beforeEach(() => {
      store.set(copilotStatusState, {
        busy: false,
        kind: null,
        message: null,
      });
    });

    it.each([
      [
        "omitted message and unknown kind",
        { kind: "Inactive", busy: false },
        { busy: false, kind: "Inactive", message: null, status: undefined },
      ],
      [
        "omitted busy",
        { kind: "Error", message: "Not signed in" },
        {
          busy: false,
          kind: "Error",
          message: "Not signed in",
          status: undefined,
        },
      ],
      [
        "a fully populated payload",
        {
          busy: true,
          kind: "Normal",
          message: "Working",
          status: "InProgress",
        },
        {
          busy: true,
          kind: "Normal",
          message: "Working",
          status: "InProgress",
        },
      ],
      [
        "unusable field types",
        { busy: 1, kind: 2, message: 3, status: 4 },
        { busy: false, kind: null, message: null, status: undefined },
      ],
    ])(
      "normalizes rather than discards a status update with %s",
      async (_label, params, expected) => {
        const client = new CopilotLanguageServerClient({
          rootUri: "file:///test",
          workspaceFolders: null,
          transport: mockTransport,
        });
        await client.initializePromise;

        mockTransport.emit({
          jsonrpc: "2.0",
          method: "didChangeStatus",
          params,
        });

        expect(store.get(copilotStatusState)).toEqual(expected);
      },
    );

    it("ignores a status update with non-object params", async () => {
      const client = new CopilotLanguageServerClient({
        rootUri: "file:///test",
        workspaceFolders: null,
        transport: mockTransport,
      });
      await client.initializePromise;

      mockTransport.emit({
        jsonrpc: "2.0",
        method: "statusNotification",
        params: "not-an-object",
      });

      expect(store.get(copilotStatusState)).toEqual({
        busy: false,
        kind: null,
        message: null,
      });
    });
  });
});
