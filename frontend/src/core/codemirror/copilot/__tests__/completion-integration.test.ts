/* Copyright 2026 Marimo. All rights reserved. */

import { EditorView } from "@codemirror/view";
import {
  languageServerWithClient,
  type JSONRPCMessage,
  type JSONRPCRequest,
  type Transport,
} from "@marimo-team/codemirror-languageserver";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { API } from "@/core/network/api";
import { languageAdapterState } from "../../language/extension";
import { copilotBundle } from "../extension";
import { getCodes } from "../getCodes";
import { CopilotLanguageServerClient } from "../language-server";

const fixture: { client?: CopilotLanguageServerClient } = vi.hoisted(
  () => ({}),
);

vi.mock("../client", () => ({
  COPILOT_FILENAME: "/__marimo_copilot__.py",
  getCopilotClient: () => fixture.client,
  copilotServer: () =>
    languageServerWithClient({
      client: fixture.client!,
      documentUri: "file:///__marimo_copilot__.py",
      languageId: "python",
      sendIncrementalChanges: false,
      hoverEnabled: false,
      completionEnabled: false,
      diagnosticsEnabled: false,
      signatureHelpEnabled: false,
    }),
}));
vi.mock("../state", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../state")>()),
  isCopilotEnabled: () => true,
}));
vi.mock("../getCodes", () => ({
  getCodes: vi.fn((code: string) => `import math\n\n${code}`),
}));

describe("Copilot editor integration", () => {
  let view: EditorView;
  let client: CopilotLanguageServerClient;
  let emit: (message: JSONRPCMessage) => void;
  let sent: JSONRPCMessage[];

  function requests() {
    return sent.filter(
      (message): message is JSONRPCRequest =>
        "id" in message &&
        "method" in message &&
        message.method === "textDocument/inlineCompletion",
    );
  }
  function type(text: string) {
    const from = view.state.selection.main.head;
    view.dispatch({
      changes: { from, insert: text },
      selection: { anchor: from + text.length },
    });
  }
  function respond(text: string) {
    emit({
      jsonrpc: "2.0",
      id: requests().at(-1)!.id,
      result: [{ insertText: text }],
    });
  }

  function useCustomEditor() {
    view.destroy();
    view = new EditorView({
      parent: document.body,
      doc: "pri",
      selection: { anchor: 3 },
      extensions: [
        languageAdapterState,
        copilotBundle({
          copilot: "custom",
          activate_on_typing: true,
          signature_hint_on_typing: false,
        }),
      ],
    });
    vi.spyOn(view, "hasFocus", "get").mockReturnValue(true);
  }

  beforeEach(async () => {
    vi.useFakeTimers();
    // copilotBundle intentionally disables itself in ordinary unit tests.
    vi.stubEnv("NODE_ENV", "development");
    sent = [];
    const transport: Transport = {
      connect: vi.fn().mockResolvedValue(undefined),
      close: vi.fn(),
      onMessage: (handler) => {
        emit = handler;
        return vi.fn();
      },
      send: (message) => {
        sent.push(message);
        if (
          "id" in message &&
          "method" in message &&
          ["initialize", "shutdown"].includes(message.method)
        ) {
          emit({
            jsonrpc: "2.0",
            id: message.id,
            result:
              message.method === "initialize"
                ? { capabilities: { textDocumentSync: 1 } }
                : null,
          });
        }
      },
    };
    client = new CopilotLanguageServerClient({
      rootUri: "file:///",
      workspaceFolders: null,
      transport,
    });
    fixture.client = client;
    await client.initializePromise;
    view = new EditorView({
      parent: document.body,
      doc: "pri",
      selection: { anchor: 3 },
      extensions: copilotBundle({
        copilot: "github",
        activate_on_typing: true,
        signature_hint_on_typing: false,
      }),
    });
    vi.spyOn(view, "hasFocus", "get").mockReturnValue(true);
    await vi.advanceTimersByTimeAsync(0);
    sent.length = 0;
    vi.mocked(getCodes).mockClear();
  });

  afterEach(() => {
    view.destroy();
    client.close();
    fixture.client = undefined;
    vi.useRealTimers();
    vi.unstubAllEnvs();
    vi.restoreAllMocks();
  });

  it("uploads once and requests the matching version/position at 150ms without an extra sleep", async () => {
    type("n");
    type("t");
    await vi.advanceTimersByTimeAsync(149);
    expect(sent).toEqual([]);
    expect(getCodes).not.toHaveBeenCalled();
    await vi.advanceTimersByTimeAsync(1);
    expect(getCodes).toHaveBeenCalledExactlyOnceWith("print");
    expect(sent).toEqual([
      {
        jsonrpc: "2.0",
        method: "textDocument/didChange",
        params: {
          textDocument: { uri: "file:///__marimo_copilot__.py", version: 2 },
          contentChanges: [{ text: "import math\n\nprint" }],
        },
      },
      {
        jsonrpc: "2.0",
        id: expect.any(Number),
        method: "textDocument/inlineCompletion",
        params: {
          textDocument: { uri: "file:///__marimo_copilot__.py", version: 2 },
          position: { line: 2, character: 5 },
          context: { triggerKind: 2 },
          formattingOptions: { tabSize: 4, insertSpaces: true },
        },
      },
    ]);
    respond("(value)");
    await vi.advanceTimersByTimeAsync(0);
    expect(view.dom.querySelector(".cm-inline-suggestion")).toHaveTextContent(
      "(value)",
    );
    type("(");
    expect(view.dom.querySelector(".cm-inline-suggestion")).toHaveTextContent(
      "value)",
    );
    await vi.advanceTimersByTimeAsync(500);
    expect(requests()).toHaveLength(1);
    expect(getCodes).toHaveBeenCalledTimes(1);
    type("x");
    await vi.advanceTimersByTimeAsync(150);
    expect(getCodes).toHaveBeenLastCalledWith("print(x");
    expect(requests()).toHaveLength(2);
    respond(")");
    await vi.advanceTimersByTimeAsync(0);
    expect(view.dom.querySelector(".cm-inline-suggestion")).toHaveTextContent(
      ")",
    );
  });

  it("never uploads a superseded snapshot when typing restarts the debounce", async () => {
    const flush = vi.spyOn(client, "flushDocumentChanges");
    type("n");
    await vi.advanceTimersByTimeAsync(149);
    type("t");
    await vi.advanceTimersByTimeAsync(149);
    expect(flush).not.toHaveBeenCalled();
    expect(getCodes).not.toHaveBeenCalled();
    expect(sent).toEqual([]);
    await vi.advanceTimersByTimeAsync(1);
    expect(flush.mock.calls.filter(([code]) => code !== undefined)).toEqual([
      ["print"],
    ]);
    expect(getCodes).toHaveBeenCalledExactlyOnceWith("print");
    expect(
      sent.filter(
        (message) =>
          "method" in message && message.method === "textDocument/didChange",
      ),
    ).toEqual([
      {
        jsonrpc: "2.0",
        method: "textDocument/didChange",
        params: {
          textDocument: { uri: "file:///__marimo_copilot__.py", version: 2 },
          contentChanges: [{ text: "import math\n\nprint" }],
        },
      },
    ]);
    expect(requests()).toHaveLength(1);
    respond("(latest)");
    await vi.advanceTimersByTimeAsync(0);
    expect(view.dom.querySelector(".cm-inline-suggestion")).toHaveTextContent(
      "(latest)",
    );
  });

  it("does not flush a cancelled callback after moving away and back before its deadline", async () => {
    const flush = vi.spyOn(client, "flushDocumentChanges");
    type("n");
    await vi.advanceTimersByTimeAsync(149);
    view.dispatch({ selection: { anchor: 0 } });
    view.dispatch({ selection: { anchor: 4 } });
    await vi.advanceTimersByTimeAsync(1000);
    expect(flush).not.toHaveBeenCalled();
    expect(getCodes).not.toHaveBeenCalled();
    expect(sent).toEqual([]);
    expect(view.dom.querySelector(".cm-inline-suggestion")).toBeNull();
  });

  it("cancels on cursor movement and never shows an old reply", async () => {
    type("n");
    await vi.advanceTimersByTimeAsync(150);
    view.dispatch({ selection: { anchor: 0 } });
    await vi.advanceTimersByTimeAsync(0);
    expect(sent.at(-1)).toEqual({
      jsonrpc: "2.0",
      method: "$/cancelRequest",
      params: { id: requests()[0].id },
    });
    respond("stale");
    await vi.advanceTimersByTimeAsync(0);
    expect(view.dom.querySelector(".cm-inline-suggestion")).toBeNull();
  });

  it("cancels an in-flight suggestion on typing before requesting the next version", async () => {
    type("n");
    await vi.advanceTimersByTimeAsync(150);
    type("t");
    await vi.advanceTimersByTimeAsync(0);
    expect(sent.at(-1)).toEqual({
      jsonrpc: "2.0",
      method: "$/cancelRequest",
      params: { id: requests()[0].id },
    });
    await vi.advanceTimersByTimeAsync(150);
    respond("(new)");
    await vi.advanceTimersByTimeAsync(0);
    emit({
      jsonrpc: "2.0",
      id: requests()[0].id,
      result: [{ insertText: "stale" }],
    });
    await vi.advanceTimersByTimeAsync(0);
    expect(view.dom.querySelector(".cm-inline-suggestion")).toHaveTextContent(
      "(new)",
    );
  });
  it("does not display a response after focus is lost", async () => {
    type("n");
    await vi.advanceTimersByTimeAsync(150);
    vi.spyOn(view, "hasFocus", "get").mockReturnValue(false);
    respond("stale");
    await vi.advanceTimersByTimeAsync(0);
    expect(view.dom.querySelector(".cm-inline-suggestion")).toBeNull();
  });

  it("passes cancellation through to custom provider HTTP requests", async () => {
    const result = Promise.withResolvers<string>();
    const post = vi.spyOn(API, "post").mockReturnValue(result.promise);
    useCustomEditor();
    type("n");
    await vi.advanceTimersByTimeAsync(150);
    expect(post).toHaveBeenCalledExactlyOnceWith(
      "/ai/inline_completion",
      { prefix: "prin", suffix: "", language: "python" },
      { signal: expect.objectContaining({ aborted: false }) },
    );
    const signal = post.mock.calls[0][2]?.signal;
    type("t");
    expect(signal?.aborted).toBe(true);
    result.resolve("stale");
    await vi.advanceTimersByTimeAsync(0);
    expect(view.dom.querySelector(".cm-inline-suggestion")).toBeNull();
  });
  it.each(["HTTP failure", "AbortError"])(
    "recovers on the next edit after custom provider %s",
    async (failure) => {
      useCustomEditor();
      const error = vi
        .spyOn(console, "error")
        .mockImplementation(() => undefined);
      const post = vi
        .spyOn(API, "post")
        .mockRejectedValueOnce(
          failure === "AbortError"
            ? new DOMException("aborted", "AbortError")
            : new Error("HTTP 503"),
        )
        .mockResolvedValueOnce("(recovered)");
      type("n");
      await vi.advanceTimersByTimeAsync(150);
      expect(post).toHaveBeenCalledTimes(1);
      expect(view.dom.querySelector(".cm-inline-suggestion")).toBeNull();
      expect(error).toHaveBeenCalledTimes(failure === "AbortError" ? 0 : 1);
      type("t");
      await vi.advanceTimersByTimeAsync(150);
      expect(post).toHaveBeenCalledTimes(2);
      expect(view.dom.querySelector(".cm-inline-suggestion")).toHaveTextContent(
        "(recovered)",
      );
    },
  );

  it.each(["empty document", "empty prefix"])(
    "does not call the custom provider for an %s",
    async (input) => {
      useCustomEditor();
      const post = vi.spyOn(API, "post").mockResolvedValue("unexpected");
      view.dispatch({
        changes: {
          from: 0,
          to: view.state.doc.length,
          insert: input === "empty document" ? "" : "suffix",
        },
        selection: { anchor: 0 },
      });
      await vi.advanceTimersByTimeAsync(150);
      expect(post).not.toHaveBeenCalled();
      expect(view.dom.querySelector(".cm-inline-suggestion")).toBeNull();
    },
  );

  it("aborts custom provider HTTP work when its editor is destroyed", async () => {
    useCustomEditor();
    const result = Promise.withResolvers<string>();
    const post = vi.spyOn(API, "post").mockReturnValue(result.promise);
    const error = vi
      .spyOn(console, "error")
      .mockImplementation(() => undefined);
    type("n");
    await vi.advanceTimersByTimeAsync(150);
    expect(post).toHaveBeenCalledTimes(1);
    const signal = post.mock.calls[0][2]?.signal;
    expect(signal?.aborted).toBe(false);
    view.destroy();
    expect(signal?.aborted).toBe(true);
    result.reject(new Error("connection closed after destruction"));
    await vi.advanceTimersByTimeAsync(150);
    expect(post).toHaveBeenCalledTimes(1);
    expect(error).not.toHaveBeenCalled();
  });

  it.each(["server error", "timeout"])(
    "recovers on the next edit after a Copilot %s",
    async (failure) => {
      type("n");
      await vi.advanceTimersByTimeAsync(150);
      expect(requests()).toHaveLength(1);
      const id = requests()[0].id;
      if (failure === "timeout") {
        await vi.advanceTimersByTimeAsync(10_000);
      } else {
        emit({
          jsonrpc: "2.0",
          id,
          error: { code: -32603, message: "unavailable" },
        });
        await vi.advanceTimersByTimeAsync(0);
      }
      expect(
        sent.filter(
          (message) =>
            "method" in message && message.method === "$/cancelRequest",
        ),
      ).toEqual(
        failure === "timeout"
          ? [{ jsonrpc: "2.0", method: "$/cancelRequest", params: { id } }]
          : [],
      );
      expect(view.dom.querySelector(".cm-inline-suggestion")).toBeNull();
      type("t");
      await vi.advanceTimersByTimeAsync(150);
      expect(requests()).toHaveLength(2);
      respond("(recovered)");
      await vi.advanceTimersByTimeAsync(0);
      emit({ jsonrpc: "2.0", id, result: [{ insertText: "stale" }] });
      await vi.advanceTimersByTimeAsync(0);
      expect(view.dom.querySelector(".cm-inline-suggestion")).toHaveTextContent(
        "(recovered)",
      );
    },
  );

  it("keeps the focused cell last when another cell changes during the debounce", async () => {
    type("n");
    await client.textDocumentDidChange({
      textDocument: { uri: "file:///__marimo_copilot__.py", version: 1 },
      contentChanges: [{ text: "other_cell = 42" }],
    });
    await vi.advanceTimersByTimeAsync(150);
    expect(getCodes).toHaveBeenCalledExactlyOnceWith("prin");
    expect(requests()[0].params).toMatchObject({
      textDocument: { version: 3 },
      position: { line: 2, character: 4 },
    });
    respond("t()");
    await vi.advanceTimersByTimeAsync(0);
    expect(view.dom.querySelector(".cm-inline-suggestion")).toHaveTextContent(
      "t()",
    );
  });
});
