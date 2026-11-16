/* Copyright 2026 Marimo. All rights reserved. */
import type {
  JSONRPCMessage,
  JSONRPCNotification,
  JSONRPCRequest,
  Transport,
} from "@marimo-team/codemirror-languageserver";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { InlineCompletionParams } from "vscode-languageserver-protocol";
import { store } from "@/core/state/jotai";
import * as notebookCodes from "../getCodes";
import { CopilotLanguageServerClient } from "../language-server";
import { copilotStatusState, githubCopilotLoadingVersion } from "../state";

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
  public readonly sent: JSONRPCMessage[] = [];

  public connect = vi.fn().mockResolvedValue(undefined);
  public close = vi.fn();
  public send = vi.fn((message: JSONRPCMessage) => {
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

  public onMessage(handler: (message: JSONRPCMessage) => void): () => void {
    this.handlers.add(handler);
    return () => {
      this.handlers.delete(handler);
    };
  }

  public emit(message: JSONRPCMessage) {
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

  it("does not close the shared document until the last mounted editor closes it (relies on base client's own refcounting)", async () => {
    const client = new CopilotLanguageServerClient({
      rootUri: "file:///test",
      workspaceFolders: null,
      transport: mockTransport,
    });
    await client.initializePromise;

    // Two editors (e.g. two visible cells) share this client and both open
    // the same document.
    await client.textDocumentDidOpen({
      textDocument: {
        uri: "file:///test.py",
        languageId: "python",
        version: 1,
        text: "value = 1",
      },
    });
    await client.textDocumentDidOpen({
      textDocument: {
        uri: "file:///test.py",
        languageId: "python",
        version: 1,
        text: "value = 1",
      },
    });
    mockTransport.sent.length = 0;

    // Closing the first editor must not close the shared document while the
    // second editor is still mounted.
    await client.textDocumentDidClose({
      textDocument: { uri: "file:///test.py" },
    });
    expect(notifications(mockTransport, "textDocument/didClose")).toEqual([]);

    // Closing the last editor closes the document for real.
    await client.textDocumentDidClose({
      textDocument: { uri: "file:///test.py" },
    });
    expect(notifications(mockTransport, "textDocument/didClose")).toEqual([
      {
        jsonrpc: "2.0",
        method: "textDocument/didClose",
        params: { textDocument: { uri: "file:///test.py" } },
      },
    ]);
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

    await client.flushDocumentChanges();
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

describe("Copilot completion requests", () => {
  let transport: MockTransport;
  let client: CopilotLanguageServerClient;
  const params: InlineCompletionParams = {
    textDocument: { uri: "file:///test.py" },
    position: { line: 0, character: 1 },
    context: { triggerKind: 2 },
  };
  const suggestion = [{ insertText: "result" }];

  function requests() {
    return transport.sent.filter(
      (message): message is JSONRPCRequest =>
        isRequest(message) &&
        message.method === "textDocument/inlineCompletion",
    );
  }

  async function change(text: string) {
    await client.textDocumentDidChange({
      textDocument: { uri: params.textDocument.uri, version: 1 },
      contentChanges: [{ text }],
    });
  }

  async function tick() {
    await vi.advanceTimersByTimeAsync(0);
  }

  beforeEach(async () => {
    vi.useFakeTimers();
    copilotState.isEnabled = true;
    store.set(githubCopilotLoadingVersion, null);
    transport = new MockTransport();
    client = new CopilotLanguageServerClient({
      rootUri: "file:///test",
      workspaceFolders: null,
      transport,
    });
    await client.initializePromise;
    await client.textDocumentDidOpen({
      textDocument: {
        uri: params.textDocument.uri,
        languageId: "python",
        version: 1,
        text: "x",
      },
    });
    transport.sent.length = 0;
  });

  afterEach(() => {
    client.close();
    const shutdown = transport.sent.find(
      (message) => isRequest(message) && message.method === "shutdown",
    );
    if (shutdown && isRequest(shutdown)) {
      transport.emit({ jsonrpc: "2.0", id: shutdown.id, result: null });
    }
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it("coalesces edits and sends the latest document before the completion", async () => {
    for (const text of ["p", "pr", "pri", "prin", "print"]) {
      await change(text);
    }
    expect(notifications(transport, "textDocument/didChange")).toEqual([]);
    const response = client.getCompletion(params);
    await tick();
    expect(transport.sent).toEqual([
      {
        jsonrpc: "2.0",
        method: "textDocument/didChange",
        params: {
          textDocument: { uri: params.textDocument.uri, version: 6 },
          contentChanges: [{ text: "print" }],
        },
      },
      {
        jsonrpc: "2.0",
        id: expect.any(Number),
        method: "textDocument/inlineCompletion",
        params: {
          ...params,
          textDocument: { uri: params.textDocument.uri, version: 6 },
        },
      },
    ]);
    transport.emit({
      jsonrpc: "2.0",
      id: requests()[0].id,
      result: suggestion,
    });
    await expect(response).resolves.toEqual(suggestion);
    expect(store.get(githubCopilotLoadingVersion)).toBeNull();
    expect(await client.flushDocumentChanges()).toBe("print");
    expect(notifications(transport, "textDocument/didChange")).toHaveLength(1);
  });

  it.each(["x", ""])(
    "does not upload an unchanged focused cell %j again",
    async (text) => {
      const assemble = vi.spyOn(notebookCodes, "getCodes");
      await change(text);
      expect(await client.flushDocumentChanges(text)).toBe(text);
      expect(await client.flushDocumentChanges(text)).toBe(text);
      expect(await client.flushDocumentChanges(text)).toBe(text);
      expect(assemble).toHaveBeenCalledTimes(3);
      expect(notifications(transport, "textDocument/didChange")).toEqual([
        {
          jsonrpc: "2.0",
          method: "textDocument/didChange",
          params: {
            textDocument: { uri: params.textDocument.uri, version: 2 },
            contentChanges: [{ text }],
          },
        },
      ]);

      await change("next");
      await client.flushDocumentChanges("next");
      expect(
        notifications(transport, "textDocument/didChange")[1].params,
      ).toEqual({
        textDocument: { uri: params.textDocument.uri, version: 3 },
        contentChanges: [{ text: "next" }],
      });
    },
  );

  it("does not upload a document that already matches didOpen", async () => {
    expect(await client.flushDocumentChanges("x")).toBe("x");
    expect(notifications(transport, "textDocument/didChange")).toEqual([]);
  });

  it("compares the assembled notebook and uploads changes in another cell", async () => {
    let otherCell = "import math";
    const assemble = vi
      .spyOn(notebookCodes, "getCodes")
      .mockImplementation((code) => `${otherCell}\n${code}`);
    await change("x");
    expect(await client.flushDocumentChanges("x")).toBe("import math\nx");
    expect(await client.flushDocumentChanges("x")).toBe("import math\nx");
    otherCell = "import random";
    expect(await client.flushDocumentChanges("x")).toBe("import random\nx");
    expect(await client.flushDocumentChanges("x")).toBe("import random\nx");
    expect(assemble).toHaveBeenCalledTimes(4);
    expect(notifications(transport, "textDocument/didChange")).toEqual([
      {
        jsonrpc: "2.0",
        method: "textDocument/didChange",
        params: {
          textDocument: { uri: params.textDocument.uri, version: 2 },
          contentChanges: [{ text: "import math\nx" }],
        },
      },
      {
        jsonrpc: "2.0",
        method: "textDocument/didChange",
        params: {
          textDocument: { uri: params.textDocument.uri, version: 3 },
          contentChanges: [{ text: "import random\nx" }],
        },
      },
    ]);
  });

  it("assembles once with the focused cell last when another cell has a pending edit", async () => {
    const assemble = vi
      .spyOn(notebookCodes, "getCodes")
      .mockImplementation((code) => `other\n${code}`);
    await change("other");
    expect(await client.flushDocumentChanges("x")).toBe("other\nx");
    expect(assemble).toHaveBeenCalledExactlyOnceWith("x");
    expect(notifications(transport, "textDocument/didChange")).toEqual([
      {
        jsonrpc: "2.0",
        method: "textDocument/didChange",
        params: {
          textDocument: { uri: params.textDocument.uri, version: 3 },
          contentChanges: [{ text: "other\nx" }],
        },
      },
    ]);
  });

  it("retries a failed upload even when its text matches the last attempted document", async () => {
    const assemble = vi.spyOn(notebookCodes, "getCodes");
    transport.send.mockImplementationOnce(() => {
      throw new Error("socket closed");
    });
    await expect(client.flushDocumentChanges("latest")).rejects.toThrow(
      "socket closed",
    );
    expect(await client.flushDocumentChanges("latest")).toBe("latest");
    expect(await client.flushDocumentChanges("latest")).toBe("latest");
    expect(assemble).toHaveBeenCalledTimes(3);
    expect(notifications(transport, "textDocument/didChange")).toEqual([
      {
        jsonrpc: "2.0",
        method: "textDocument/didChange",
        params: {
          textDocument: { uri: params.textDocument.uri, version: 2 },
          contentChanges: [{ text: "latest" }],
        },
      },
    ]);
  });

  it("cancels a rapid request instead of giving the next caller its promise", async () => {
    const first = client.getCompletion(params);
    await tick();
    const second = client.getCompletion({
      ...params,
      position: { line: 0, character: 0 },
    });
    await tick();
    expect(requests()).toHaveLength(2);
    expect(notifications(transport, "$/cancelRequest")).toEqual([
      {
        jsonrpc: "2.0",
        method: "$/cancelRequest",
        params: { id: requests()[0].id },
      },
    ]);
    await expect(first).resolves.toBeNull();
    // Both requests use the same version; old cleanup must not hide the new spinner.
    expect(store.get(githubCopilotLoadingVersion)).toBe(1);
    transport.emit({
      jsonrpc: "2.0",
      id: requests()[1].id,
      result: suggestion,
    });
    await expect(second).resolves.toEqual(suggestion);
    transport.emit({
      jsonrpc: "2.0",
      id: requests()[0].id,
      result: [{ insertText: "stale" }],
    });
    expect(store.get(githubCopilotLoadingVersion)).toBeNull();
  });

  it("suppresses a request superseded before it reaches the wire", async () => {
    const first = client.getCompletion(params);
    const second = client.getCompletion(params);
    await tick();
    expect(requests()).toHaveLength(1);
    await expect(first).resolves.toBeNull();
    transport.emit({
      jsonrpc: "2.0",
      id: requests()[0].id,
      result: suggestion,
    });
    await expect(second).resolves.toEqual(suggestion);
  });

  it("aborts on an edit before any replacement completion is requested", async () => {
    const response = client.getCompletion(params);
    await tick();
    await change("changed");
    await expect(response).resolves.toBeNull();
    expect(notifications(transport, "$/cancelRequest")).toHaveLength(1);
    expect(notifications(transport, "textDocument/didChange")).toEqual([]);
    expect(store.get(githubCopilotLoadingVersion)).toBeNull();
  });

  it.each([false, true])(
    "handles external cancellation (already sent: %s)",
    async (sent) => {
      const controller = new AbortController();
      if (!sent) {
        controller.abort();
      }
      const response = client.getCompletion(params, controller.signal);
      if (sent) {
        await tick();
        controller.abort();
      }
      await expect(response).resolves.toBeNull();
      expect(requests()).toHaveLength(sent ? 1 : 0);
      expect(notifications(transport, "$/cancelRequest")).toHaveLength(
        sent ? 1 : 0,
      );
      expect(store.get(githubCopilotLoadingVersion)).toBeNull();
    },
  );

  it.each([null, [], { items: [] }])(
    "handles empty response %j",
    async (result) => {
      const response = client.getCompletion(params);
      await tick();
      transport.emit({ jsonrpc: "2.0", id: requests()[0].id, result });
      await expect(response).resolves.toEqual(result);
      expect(store.get(githubCopilotLoadingVersion)).toBeNull();
    },
  );

  it("fails quietly on a server error and allows a subsequent request", async () => {
    const response = client.getCompletion(params);
    await tick();
    transport.emit({
      jsonrpc: "2.0",
      id: requests()[0].id,
      error: { code: -32603, message: "unavailable" },
    });
    await expect(response).resolves.toBeNull();
    const retry = client.getCompletion(params);
    await tick();
    transport.emit({
      jsonrpc: "2.0",
      id: requests()[1].id,
      result: suggestion,
    });
    await expect(retry).resolves.toEqual(suggestion);
  });

  it("cancels a timed-out request and clears its loading state", async () => {
    const response = client.getCompletion(params);
    await vi.advanceTimersByTimeAsync(10_000);
    await expect(response).resolves.toBeNull();
    expect(notifications(transport, "$/cancelRequest")).toHaveLength(1);
    expect(store.get(githubCopilotLoadingVersion)).toBeNull();
  });

  it("does not send requests while disabled or display a response after disabling", async () => {
    copilotState.isEnabled = false;
    await expect(client.getCompletion(params)).resolves.toBeNull();
    expect(requests()).toEqual([]);
    copilotState.isEnabled = true;
    const response = client.getCompletion(params);
    await tick();
    copilotState.isEnabled = false;
    transport.emit({
      jsonrpc: "2.0",
      id: requests()[0].id,
      result: suggestion,
    });
    await expect(response).resolves.toBeNull();
  });

  it("preserves pending edits after a failed document upload and retries them", async () => {
    await change("latest");
    transport.send.mockImplementationOnce(() => {
      throw new Error("socket closed");
    });
    await expect(client.getCompletion(params)).resolves.toBeNull();
    expect(requests()).toEqual([]);
    const response = client.getCompletion(params);
    await tick();
    expect(notifications(transport, "textDocument/didChange")).toEqual([
      {
        jsonrpc: "2.0",
        method: "textDocument/didChange",
        params: {
          textDocument: { uri: params.textDocument.uri, version: 2 },
          contentChanges: [{ text: "latest" }],
        },
      },
    ]);
    transport.emit({
      jsonrpc: "2.0",
      id: requests()[0].id,
      result: suggestion,
    });
    await expect(response).resolves.toEqual(suggestion);
  });

  it.each(["success", "failure"])(
    "cancels a request during a stalled reconnect before handshake %s",
    async (outcome) => {
      transport.send.mockImplementationOnce((message) => {
        transport.sent.push(message);
      });
      const reconnect = client.reInitialize().then(
        () => "ready",
        (error: unknown) => error,
      );
      const initialize = transport.sent.find(
        (message) => isRequest(message) && message.method === "initialize",
      );
      if (!initialize || !isRequest(initialize)) {
        throw new Error("Expected initialize request");
      }
      const controller = new AbortController();
      const remove = vi.spyOn(controller.signal, "removeEventListener");
      const settled = vi.fn();
      const response = client
        .getCompletion(params, controller.signal)
        .then(settled);
      await tick();
      expect(settled).not.toHaveBeenCalled();
      expect(requests()).toEqual([]);
      expect(store.get(githubCopilotLoadingVersion)).toBe(1);
      controller.abort();
      await tick();
      // Assert before answering initialize so the handshake cannot hide a stuck abort.
      expect(settled).toHaveBeenCalledExactlyOnceWith(null);
      expect(remove).toHaveBeenCalledExactlyOnceWith(
        "abort",
        expect.any(Function),
      );
      expect(store.get(githubCopilotLoadingVersion)).toBeNull();
      expect(notifications(transport, "$/cancelRequest")).toEqual([]);
      transport.emit(
        outcome === "success"
          ? {
              jsonrpc: "2.0",
              id: initialize.id,
              result: { capabilities: {} },
            }
          : {
              jsonrpc: "2.0",
              id: initialize.id,
              error: { code: -32603, message: "handshake failed" },
            },
      );
      const handshakeError = expect.objectContaining({
        message: "handshake failed",
      });
      await expect(reconnect).resolves.toEqual(
        outcome === "success" ? "ready" : handshakeError,
      );
      expect(requests()).toEqual([]);
      let retryResult: unknown;
      if (outcome === "success") {
        const retry = client.getCompletion(params);
        await tick();
        transport.emit({
          jsonrpc: "2.0",
          id: requests()[0].id,
          result: suggestion,
        });
        retryResult = await retry;
      }
      expect(requests()).toHaveLength(outcome === "success" ? 1 : 0);
      expect(retryResult).toEqual(
        outcome === "success" ? suggestion : undefined,
      );
      await response;
      expect(settled).toHaveBeenCalledTimes(1);
    },
  );

  it("replays the most recent unsent edit on reconnect", async () => {
    await change("first");
    await change("latest");
    await client.reInitialize();
    expect(notifications(transport, "textDocument/didOpen")).toEqual([
      {
        jsonrpc: "2.0",
        method: "textDocument/didOpen",
        params: {
          textDocument: {
            uri: params.textDocument.uri,
            languageId: "python",
            version: 3,
            text: "latest",
          },
        },
      },
    ]);
    expect(notifications(transport, "textDocument/didChange")).toEqual([]);
  });

  it("cancels requests and drops pending changes when the final editor closes", async () => {
    const response = client.getCompletion(params);
    await tick();
    await client.textDocumentDidClose({ textDocument: params.textDocument });
    await expect(response).resolves.toBeNull();
    await change("unsent");
    await client.textDocumentDidClose({ textDocument: params.textDocument });
    await client.flushDocumentChanges();
    expect(notifications(transport, "textDocument/didChange")).toEqual([]);
  });
  it("does not request completions for a closed document", async () => {
    await client.textDocumentDidClose({ textDocument: params.textDocument });
    await expect(client.getCompletion(params)).resolves.toBeNull();
    expect(requests()).toEqual([]);
    expect(store.get(githubCopilotLoadingVersion)).toBeNull();
  });

  it("keeps a newer edit when an earlier upload fails", async () => {
    await change("old");
    transport.send.mockImplementationOnce(() => {
      void change("new");
      throw new Error("send failed");
    });
    await expect(client.flushDocumentChanges("old")).rejects.toThrow(
      "send failed",
    );
    expect(await client.flushDocumentChanges("new")).toBe("new");
    expect(notifications(transport, "textDocument/didChange")).toEqual([
      {
        jsonrpc: "2.0",
        method: "textDocument/didChange",
        params: {
          textDocument: { uri: params.textDocument.uri, version: 3 },
          contentChanges: [{ text: "new" }],
        },
      },
    ]);
  });
});
