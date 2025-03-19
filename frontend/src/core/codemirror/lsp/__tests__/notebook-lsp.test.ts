/* Copyright 2024 Marimo. All rights reserved. */
/* eslint-disable @typescript-eslint/no-explicit-any */
import { describe, it, expect, vi, beforeEach, type Mocked } from "vitest";
import { createNotebookLens } from "../lens";
import * as LSP from "vscode-languageserver-protocol";
import { NotebookLanguageServerClient } from "../notebook-lsp";
import { CellDocumentUri, type ILanguageServerClient } from "../types";
import type { CellId } from "@/core/cells/ids";
import { EditorView } from "@codemirror/view";
import {
  type LanguageServerClient,
  languageServerWithTransport,
} from "@marimo-team/codemirror-languageserver";

const Cells = {
  cell1: "cell1" as CellId,
  cell2: "cell2" as CellId,
  cell3: "cell3" as CellId,
};

describe("createNotebookLens", () => {
  it("should calculate correct line offsets", () => {
    const cellIds: CellId[] = [Cells.cell1, Cells.cell2, Cells.cell3];
    const codes: Record<CellId, string> = {
      [Cells.cell1]: "fileA\nfileB",
      [Cells.cell2]: "line1\nline2",
      [Cells.cell3]: "fileC",
    };
    const lens = createNotebookLens(cellIds, codes);

    const pos: LSP.Position = { line: 0, character: 0 };
    const transformed = lens.transformPosition(pos, Cells.cell2);
    expect(transformed.line).toBe(2); // After fileA\nfileB
    expect(transformed.character).toBe(0);
  });

  it("should transform ranges to merged doc", () => {
    const cellIds: CellId[] = [Cells.cell1, Cells.cell2];
    const codes: Record<CellId, string> = {
      [Cells.cell1]: "before\ntext",
      [Cells.cell2]: "cell1\ncell2",
    };
    const lens = createNotebookLens(cellIds, codes);

    const range: LSP.Range = {
      start: { line: 0, character: 0 },
      end: { line: 1, character: 5 },
    };

    const transformed = lens.transformRange(range, Cells.cell2);
    expect(transformed.start.line).toBe(2);
    expect(transformed.end.line).toBe(3);
  });

  it("should reverse ranges from merged doc", () => {
    const cellIds: CellId[] = [Cells.cell1, Cells.cell2];
    const codes: Record<CellId, string> = {
      [Cells.cell1]: "header",
      [Cells.cell2]: "test\ncode",
    };
    const lens = createNotebookLens(cellIds, codes);

    const range: LSP.Range = {
      start: { line: 1, character: 0 },
      end: { line: 2, character: 4 },
    };

    const reversed = lens.reverseRange(range, Cells.cell2);
    expect(reversed.start.line).toBe(0);
    expect(reversed.end.line).toBe(1);
  });

  it("should check if range is within cell bounds", () => {
    const cellIds: CellId[] = [Cells.cell1];
    const codes: Record<CellId, string> = {
      [Cells.cell1]: "line1\nline2\nline3",
    };
    const lens = createNotebookLens(cellIds, codes);

    expect(
      lens.isInRange(
        {
          start: { line: 0, character: 0 },
          end: { line: 2, character: 5 },
        },
        Cells.cell1,
      ),
    ).toBe(true);

    expect(
      lens.isInRange(
        {
          start: { line: 0, character: 0 },
          end: { line: 3, character: 0 },
        },
        Cells.cell1,
      ),
    ).toBe(false);
  });

  it("should join all code into merged text", () => {
    const cellIds: CellId[] = [Cells.cell1, Cells.cell2, Cells.cell3];
    const codes: Record<CellId, string> = {
      [Cells.cell1]: "a",
      [Cells.cell2]: "cell",
      [Cells.cell3]: "b",
    };
    const lens = createNotebookLens(cellIds, codes);

    expect(lens.mergedText).toBe("a\ncell\nb");
  });

  it("should handle empty cells", () => {
    const cellIds: CellId[] = [Cells.cell1, Cells.cell2];
    const codes: Record<CellId, string> = {
      [Cells.cell1]: "",
      [Cells.cell2]: "code",
    };
    const lens = createNotebookLens(cellIds, codes);

    const pos: LSP.Position = { line: 0, character: 0 };
    const transformed = lens.transformPosition(pos, Cells.cell2);
    expect(transformed.line).toBe(1);
  });

  it("should handle cells with multiple lines", () => {
    const cellIds: CellId[] = [Cells.cell1, Cells.cell2];
    const codes: Record<CellId, string> = {
      [Cells.cell1]: "line1\nline2\nline3",
      [Cells.cell2]: "test",
    };
    const lens = createNotebookLens(cellIds, codes);

    const pos: LSP.Position = { line: 0, character: 0 };
    const transformed = lens.transformPosition(pos, Cells.cell2);
    expect(transformed.line).toBe(3);
  });

  it("should clip range and text to cell boundaries", () => {
    const cellIds: CellId[] = [Cells.cell1, Cells.cell2, Cells.cell3];
    const codes: Record<CellId, string> = {
      [Cells.cell1]: "line1\nline2",
      [Cells.cell2]: "line3\nline4\nline5",
      [Cells.cell3]: "line6\nline7",
    };
    const lens = createNotebookLens(cellIds, codes);

    // Assume the line length does not change
    const newText = "a\nb\nc\nd\ne\nf\ng";

    const edits = lens.getEditsForNewText(newText);

    expect(edits).toMatchInlineSnapshot(`
      [
        {
          "cellId": "cell1",
          "text": "a
      b",
        },
        {
          "cellId": "cell2",
          "text": "c
      d
      e",
        },
        {
          "cellId": "cell3",
          "text": "f
      g",
        },
      ]
    `);
  });
});

describe("NotebookLanguageServerClient", () => {
  let plugins: any[] = [];
  let mockClient: Mocked<ILanguageServerClient>;
  let notebookClient: NotebookLanguageServerClient;

  beforeEach(() => {
    plugins = [];
    mockClient = {
      plugins,
      ready: true,
      capabilities: {},
      initializePromise: Promise.resolve(),
      initialize: vi.fn(),
      close: vi.fn(),
      detachPlugin: vi.fn().mockImplementation((plugin) => {
        plugins = plugins.filter((p) => p !== plugin);
      }),
      attachPlugin: vi.fn().mockImplementation((plugin) => {
        plugins.push(plugin);
      }),
      textDocumentDidOpen: vi.fn(),
      textDocumentDidChange: vi.fn(),
      textDocumentHover: vi.fn(),
      textDocumentCompletion: vi.fn(),
      textDocumentRename: vi.fn(),
      processNotification: vi.fn(),
      notify: vi.fn(),
      request: vi.fn(),
    } as unknown as Mocked<ILanguageServerClient>;
    notebookClient = new NotebookLanguageServerClient(mockClient, {});
    (notebookClient as any).getNotebookCode = vi.fn().mockReturnValue({
      cellIds: [Cells.cell1, Cells.cell2, Cells.cell3],
      codes: {
        [Cells.cell1]: "# this is a comment",
        [Cells.cell2]: "import math\nimport numpy",
        [Cells.cell3]: "print(math.sqrt(4))",
      },
    });
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
          textDocument: { uri: "file:///__marimo_notebook__.py" },
        }),
      );
    });
  });

  describe("textDocumentRename", () => {
    it("should transform rename position and apply edits to editor views", async () => {
      const props = {
        workspaceFolders: null,
        capabilities: {
          textDocument: {
            rename: {
              prepareSupport: true,
            },
          },
        },
        languageId: "python",
        transport: {
          sendData: vi.fn(),
          subscribe: vi.fn(),
          connect: vi.fn(),
          transportRequestManager: {
            send: vi.fn(),
          },
        } as any,
      };

      // Setup mock plugins with editor views
      const mockView1 = new EditorView({
        doc: "# this is a comment",
        extensions: [
          languageServerWithTransport({
            client: mockClient as unknown as LanguageServerClient,
            rootUri: "file:///",
            documentUri: CellDocumentUri.of(Cells.cell1),
            ...props,
          }),
        ],
      });
      expect(mockView1.state.doc.toString()).toBe("# this is a comment");

      const mockView2 = new EditorView({
        doc: "import math\nimport numpy",
        extensions: [
          languageServerWithTransport({
            client: mockClient as unknown as LanguageServerClient,
            rootUri: "file:///",
            documentUri: CellDocumentUri.of(Cells.cell2),
            ...props,
          }),
        ],
      });
      expect(mockView2.state.doc.toString()).toBe("import math\nimport numpy");

      const mockView3 = new EditorView({
        doc: "print(math.sqrt(4))",
        extensions: [
          languageServerWithTransport({
            client: mockClient as unknown as LanguageServerClient,
            rootUri: "file:///",
            documentUri: CellDocumentUri.of(Cells.cell3),
            ...props,
          }),
        ],
      });
      expect(mockView3.state.doc.toString()).toBe("print(math.sqrt(4))");

      // Setup rename params
      const renameParams: LSP.RenameParams = {
        textDocument: { uri: CellDocumentUri.of(Cells.cell2) },
        position: { line: 0, character: 7 },
        newName: "renamed_math",
      };

      // Open a document first to set up the lens
      await notebookClient.textDocumentDidOpen({
        textDocument: {
          uri: CellDocumentUri.of(Cells.cell2),
          languageId: "python",
          version: 1,
          text: "import math\nimport numpy",
        },
      });

      // Mock the response from the language server
      const mockRenameResponse: LSP.WorkspaceEdit = {
        documentChanges: [
          {
            textDocument: {
              uri: "file:///__marimo_notebook__.py",
              version: 1,
            },
            edits: [
              {
                range: {
                  start: { line: 0, character: 0 },
                  end: { line: 5, character: 0 },
                },
                newText:
                  "# this is a comment\nimport renamed_math\nimport numpy\nprint(renamed_math.sqrt(4))",
              },
            ],
          },
        ],
      };

      mockClient.textDocumentRename = vi
        .fn()
        .mockResolvedValue(mockRenameResponse);

      // Call rename
      const result = await notebookClient.textDocumentRename(renameParams);
      expect(result).toMatchInlineSnapshot(`
        {
          "documentChanges": [
            {
              "edits": [],
              "textDocument": {
                "uri": "file:///cell2",
                "version": 0,
              },
            },
          ],
        }
      `);

      expect(mockView2.state.doc.toString()).toBe(
        "import renamed_math\nimport numpy",
      );
      expect(mockView1.state.doc.toString()).toBe("# this is a comment");
    });

    it("should return null for invalid cell document URIs", async () => {
      const invalidParams: LSP.RenameParams = {
        textDocument: { uri: "file:///invalid.py" },
        position: { line: 0, character: 0 },
        newName: "new_name",
      };

      const result = await notebookClient.textDocumentRename(invalidParams);
      expect(result).toBeNull();
    });

    it("should return null when no lens is found", async () => {
      const renameParams: LSP.RenameParams = {
        textDocument: { uri: CellDocumentUri.of(Cells.cell1) },
        position: { line: 0, character: 0 },
        newName: "new_name",
      };

      const result = await notebookClient.textDocumentRename(renameParams);
      expect(result).toBeNull();
    });

    it("should return the original response when edits are not as expected", async () => {
      // Setup response with multiple edits
      const multiEditResponse: LSP.WorkspaceEdit = {
        documentChanges: [
          {
            textDocument: {
              uri: "file:///__marimo_notebook__.py",
              version: 1,
            },
            edits: [
              {
                range: {
                  start: { line: 0, character: 0 },
                  end: { line: 0, character: 5 },
                },
                newText: "edit1",
              },
              {
                range: {
                  start: { line: 1, character: 0 },
                  end: { line: 1, character: 5 },
                },
                newText: "edit2",
              },
            ],
          },
        ],
      };

      mockClient.textDocumentRename = vi
        .fn()
        .mockResolvedValue(multiEditResponse);

      // Open a document first to set up the lens
      await notebookClient.textDocumentDidOpen({
        textDocument: {
          uri: CellDocumentUri.of(Cells.cell1),
          languageId: "python",
          version: 1,
          text: "test",
        },
      });

      const renameParams: LSP.RenameParams = {
        textDocument: { uri: CellDocumentUri.of(Cells.cell1) },
        position: { line: 0, character: 0 },
        newName: "new_name",
      };

      const result = await notebookClient.textDocumentRename(renameParams);

      // Should return the original response when edits don't meet expectations
      expect(result).toEqual(multiEditResponse);
    });

    it("should return the original response when edits don't have newText property", async () => {
      // Setup response with an edit that doesn't have newText
      const invalidEditResponse: LSP.WorkspaceEdit = {
        documentChanges: [
          {
            textDocument: {
              uri: "file:///__marimo_notebook__.py",
              version: 1,
            },
            edits: [
              {
                range: {
                  start: { line: 0, character: 0 },
                  end: { line: 0, character: 5 },
                },
                // Missing newText property
              } as any,
            ],
          },
        ],
      };

      mockClient.textDocumentRename = vi
        .fn()
        .mockResolvedValue(invalidEditResponse);

      // Open a document first to set up the lens
      await notebookClient.textDocumentDidOpen({
        textDocument: {
          uri: CellDocumentUri.of(Cells.cell1),
          languageId: "python",
          version: 1,
          text: "test",
        },
      });

      const renameParams: LSP.RenameParams = {
        textDocument: { uri: CellDocumentUri.of(Cells.cell1) },
        position: { line: 0, character: 0 },
        newName: "new_name",
      };

      const result = await notebookClient.textDocumentRename(renameParams);

      // Should return the original response when edits don't have proper properties
      expect(result).toEqual(invalidEditResponse);
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
      // Start the document version at 1
      (notebookClient as any).documentVersion = 1;

      // Open a document
      await notebookClient.textDocumentDidOpen({
        textDocument: {
          uri: CellDocumentUri.of(Cells.cell1),
          languageId: "python",
          version: 1,
          text: "import math\nimport numpy",
        },
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

    it("should clear diagnostics for all cells when receiving empty diagnostics", async () => {
      const seenNotifications: LSP.PublishDiagnosticsParams[] = [];
      (mockClient as any).processNotification = vi
        .fn()
        .mockImplementation((notification: any) => {
          if (notification.method === "textDocument/publishDiagnostics") {
            seenNotifications.push(notification.params);
          }
        });

      notebookClient.patchProcessNotification();
      // Start the document version at 1
      (notebookClient as any).documentVersion = 1;

      // Simulate receiving empty diagnostics
      const emptyDiagnosticsNotification = {
        method: "textDocument/publishDiagnostics",
        params: {
          uri: "file:///__marimo__.py",
          version: 1,
          diagnostics: [],
        },
      };

      // @ts-expect-error: processNotification is private
      notebookClient.client.processNotification(emptyDiagnosticsNotification);

      expect(seenNotifications.length).toBeGreaterThan(0);
      seenNotifications.forEach((notification) => {
        expect(notification.diagnostics).toHaveLength(0);
      });
    });

    it("should handle diagnostics across multiple cells", async () => {
      const seenNotifications = new Map<string, LSP.PublishDiagnosticsParams>();
      (mockClient as any).processNotification = vi
        .fn()
        .mockImplementation((notification: any) => {
          if (notification.method === "textDocument/publishDiagnostics") {
            seenNotifications.set(notification.params.uri, notification.params);
          }
        });

      notebookClient.patchProcessNotification();
      // Start the document version at 1
      (notebookClient as any).documentVersion = 1;

      // Open a document
      await notebookClient.textDocumentDidOpen({
        textDocument: {
          uri: CellDocumentUri.of(Cells.cell1),
          languageId: "python",
          version: 1,
          text: "import math\nimport numpy",
        },
      });

      // Simulate receiving diagnostics for multiple cells
      const multiCellDiagnosticsNotification = {
        method: "textDocument/publishDiagnostics",
        params: {
          uri: "file:///__marimo__.py",
          version: 1,
          diagnostics: [
            {
              range: {
                start: { line: 0, character: 0 },
                end: { line: 0, character: 4 },
              },
              message: "Cell 1 diagnostic",
              severity: LSP.DiagnosticSeverity.Error,
            },
            {
              range: {
                start: { line: 2, character: 0 },
                end: { line: 2, character: 4 },
              },
              message: "Cell 2 diagnostic",
              severity: LSP.DiagnosticSeverity.Warning,
            },
          ],
        },
      };

      // @ts-expect-error: processNotification is private
      notebookClient.client.processNotification(
        multiCellDiagnosticsNotification,
      );

      expect(seenNotifications.size).toBe(2);
      const cell1Uri = CellDocumentUri.of(Cells.cell1);
      const cell2Uri = CellDocumentUri.of(Cells.cell2);

      expect(seenNotifications.get(cell1Uri)?.diagnostics).toHaveLength(1);
      expect(seenNotifications.get(cell2Uri)?.diagnostics).toHaveLength(1);
      expect(seenNotifications.get(cell1Uri)?.diagnostics[0].message).toBe(
        "Cell 1 diagnostic",
      );
      expect(seenNotifications.get(cell2Uri)?.diagnostics[0].message).toBe(
        "Cell 2 diagnostic",
      );
    });

    it("should handle version updates in textDocumentDidChange", async () => {
      let capturedChange: LSP.DidChangeTextDocumentParams | undefined;
      mockClient.textDocumentDidChange = vi
        .fn()
        .mockImplementation((params) => {
          capturedChange = params;
        });

      await notebookClient.textDocumentDidChange({
        textDocument: {
          uri: CellDocumentUri.of(Cells.cell1),
          version: 5,
        },
        contentChanges: [{ text: "new code" }],
      });

      expect(capturedChange).toBeDefined();
      expect(capturedChange?.textDocument.version).toBeGreaterThan(0);
      expect(capturedChange?.contentChanges).toHaveLength(1);
      expect(capturedChange?.contentChanges[0].text).toMatchInlineSnapshot(`
        "# this is a comment
        import math
        import numpy
        print(math.sqrt(4))"
      `);
    });
  });

  describe("initialization and configuration", () => {
    it("should send configuration after initialization", async () => {
      const configNotifications: any[] = [];
      (mockClient as any).notify = vi
        .fn()
        .mockImplementation((method, params) => {
          configNotifications.push({ method, params });
        });

      // Create a new client to trigger initialization
      const client = new NotebookLanguageServerClient(mockClient, {});
      await client.initialize();

      expect(configNotifications[0]).toMatchInlineSnapshot(`
        {
          "method": "workspace/didChangeConfiguration",
          "params": {
            "settings": {},
          },
        }
      `);
    });
  });
});
