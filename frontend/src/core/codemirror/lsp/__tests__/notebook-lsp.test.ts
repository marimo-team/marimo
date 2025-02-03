/* Copyright 2024 Marimo. All rights reserved. */
/* eslint-disable @typescript-eslint/no-explicit-any */
import { describe, it, expect, vi, beforeEach, type Mocked } from "vitest";
import { createNotebookLens } from "../lens";
import * as LSP from "vscode-languageserver-protocol";
import { NotebookLanguageServerClient } from "../notebook-lsp";
import type { ILanguageServerClient } from "../types";

describe("createNotebookLens", () => {
  it("should calculate correct line offsets", () => {
    const cell = "line1\nline2";
    const allCode = ["fileA\nfileB", cell, "fileC"];
    const lens = createNotebookLens(cell, allCode);

    const pos: LSP.Position = { line: 0, character: 0 };
    const transformed = lens.transformPosition(pos);
    expect(transformed.line).toBe(2); // After fileA\nfileB
    expect(transformed.character).toBe(0);
  });

  it("should transform ranges to merged doc", () => {
    const cell = "cell1\ncell2";
    const allCode = ["before\ntext", cell];
    const lens = createNotebookLens(cell, allCode);

    const range: LSP.Range = {
      start: { line: 0, character: 0 },
      end: { line: 1, character: 5 },
    };

    const transformed = lens.transformRange(range);
    expect(transformed.start.line).toBe(2);
    expect(transformed.end.line).toBe(3);
  });

  it("should reverse ranges from merged doc", () => {
    const cell = "test\ncode";
    const allCode = ["header", cell];
    const lens = createNotebookLens(cell, allCode);

    const range: LSP.Range = {
      start: { line: 1, character: 0 },
      end: { line: 2, character: 4 },
    };

    const reversed = lens.reverseRange(range);
    expect(reversed.start.line).toBe(0);
    expect(reversed.end.line).toBe(1);
  });

  it("should check if range is within cell bounds", () => {
    const cell = "line1\nline2\nline3";
    const lens = createNotebookLens(cell, [cell]);

    expect(
      lens.isInRange({
        start: { line: 0, character: 0 },
        end: { line: 2, character: 5 },
      }),
    ).toBe(true);

    expect(
      lens.isInRange({
        start: { line: 0, character: 0 },
        end: { line: 3, character: 0 },
      }),
    ).toBe(false);
  });

  it("should join all code into merged text", () => {
    const cell = "cell";
    const allCode = ["a", cell, "b"];
    const lens = createNotebookLens(cell, allCode);

    expect(lens.mergedText).toBe("a\ncell\nb");
  });
});

describe("NotebookLanguageServerClient", () => {
  let mockClient: Mocked<ILanguageServerClient>;
  let notebookClient: NotebookLanguageServerClient;

  beforeEach(() => {
    mockClient = {
      ready: true,
      capabilities: {},
      initializePromise: Promise.resolve(),
      initialize: vi.fn(),
      close: vi.fn(),
      detachPlugin: vi.fn(),
      attachPlugin: vi.fn(),
      textDocumentDidOpen: vi.fn(),
      textDocumentDidChange: vi.fn(),
      textDocumentHover: vi.fn(),
      textDocumentCompletion: vi.fn(),
      processNotification: vi.fn(),
      notify: vi.fn(),
      request: vi.fn(),
    } as unknown as Mocked<ILanguageServerClient>;
    notebookClient = new NotebookLanguageServerClient(mockClient);
    notebookClient.getNotebookCode = vi
      .fn()
      .mockReturnValue([
        "# this is a comment",
        "import math\nimport numpy",
        "print(math.sqrt(4))",
      ]);
  });

  describe("textDocumentHover", () => {
    it("should transform hover position and range", async () => {
      const hoverParams: LSP.HoverParams = {
        textDocument: { uri: "file:///cell1.py" },
        position: { line: 1, character: 5 },
      };

      const mockHoverResponse: LSP.Hover = {
        contents: {
          kind: "markdown",
          value: "test hover",
        },
        range: {
          start: { line: 2, character: 0 },
          end: { line: 2, character: 5 },
        },
      };

      mockClient.textDocumentHover.mockResolvedValue(mockHoverResponse);

      // Open a document first to set up the lens
      await notebookClient.textDocumentDidOpen({
        textDocument: {
          uri: "file:///cell1.py",
          languageId: "python",
          version: 1,
          text: "test\ncode",
        },
      });

      const result = await notebookClient.textDocumentHover(hoverParams);

      expect(result).toBeDefined();
      expect(result?.contents).toEqual({
        kind: "markdown",
        value:
          '<div class="docs-documentation mo-cm-tooltip">\ntest hover\n</div>',
      });
    });

    it("should return null for empty hover contents", async () => {
      const hoverParams: LSP.HoverParams = {
        textDocument: { uri: "file:///cell1.py" },
        position: { line: 0, character: 0 },
      };

      mockClient.textDocumentHover.mockResolvedValue({ contents: "" });

      await notebookClient.textDocumentDidOpen({
        textDocument: {
          uri: "file:///cell1.py",
          languageId: "python",
          version: 1,
          text: "test",
        },
      });

      const result = await notebookClient.textDocumentHover(hoverParams);
      expect(result).toBeNull();
    });
  });

  describe("textDocumentCompletion", () => {
    it("should transform completion position", async () => {
      const completionParams: LSP.CompletionParams = {
        textDocument: { uri: "file:///cell1.py" },
        position: { line: 0, character: 4 },
      };

      const mockCompletionResponse: LSP.CompletionList = {
        isIncomplete: false,
        items: [
          {
            label: "test_completion",
            kind: LSP.CompletionItemKind.Function,
          },
        ],
      };

      mockClient.textDocumentCompletion.mockResolvedValue(
        mockCompletionResponse,
      );

      await notebookClient.textDocumentDidOpen({
        textDocument: {
          uri: "file:///cell1.py",
          languageId: "python",
          version: 1,
          text: "test",
        },
      });

      const result =
        await notebookClient.textDocumentCompletion(completionParams);
      expect(result).toEqual(mockCompletionResponse);
      expect(mockClient.textDocumentCompletion).toHaveBeenCalledWith(
        expect.objectContaining({
          textDocument: { uri: "file:///__marimo__.py" },
        }),
      );
    });
  });

  describe("diagnostics handling", () => {
    it("should transform diagnostic ranges and filter out-of-bounds diagnostics", async () => {
      // Mock processNotification to capture the transformed diagnostics
      let capturedDiagnostics: LSP.PublishDiagnosticsParams | undefined;
      // @ts-expect-error: processNotification is private
      mockClient.processNotification = vi
        .fn()
        .mockImplementation((notification: any) => {
          if (notification.method === "textDocument/publishDiagnostics") {
            capturedDiagnostics = notification.params;
          }
        });

      // Call patch since we changed processNotification
      notebookClient.patchProcessNotification();

      // Open a document
      await notebookClient.textDocumentDidChange({
        textDocument: {
          uri: "file:///cell1.py",
          version: 1,
        },
        contentChanges: [
          {
            text: "import math\nimport numpy",
          },
        ],
      });

      // Simulate receiving diagnostics
      const diagnosticsNotification = {
        method: "textDocument/publishDiagnostics",
        params: {
          uri: "file:///__marimo__.py",
          version: 1,
          diagnostics: [
            {
              range: {
                start: { line: 1, character: 0 },
                end: { line: 1, character: 4 },
              },
              message: "Test diagnostic",
              severity: LSP.DiagnosticSeverity.Error,
            },
            // Out of bounds diagnostic that should be filtered
            {
              range: {
                start: { line: 10, character: 0 },
                end: { line: 10, character: 4 },
              },
              message: "Out of bounds",
              severity: LSP.DiagnosticSeverity.Error,
            },
          ],
        },
      };

      // @ts-expect-error: processNotification is private
      notebookClient.client.processNotification(diagnosticsNotification);

      expect(capturedDiagnostics).toBeDefined();
      expect(capturedDiagnostics?.diagnostics).toHaveLength(1);
      expect(capturedDiagnostics?.diagnostics[0].range).toEqual({
        start: { line: 0, character: 0 },
        end: { line: 0, character: 4 },
      });
    });
  });
});
