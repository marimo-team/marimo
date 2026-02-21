/* Copyright 2026 Marimo. All rights reserved. */
/* eslint-disable @typescript-eslint/no-explicit-any */

import { EditorView } from "@codemirror/view";
import {
  type LanguageServerClient,
  languageServerWithClient,
} from "@marimo-team/codemirror-languageserver";
import { beforeEach, describe, expect, it, type Mocked, vi } from "vitest";
import * as LSP from "vscode-languageserver-protocol";
import type { CellId } from "@/core/cells/ids";
import { store } from "@/core/state/jotai";
import { topologicalCodesAtom } from "../../copilot/getCodes";
import { languageAdapterState } from "../../language/extension";
import { PythonLanguageAdapter } from "../../language/languages/python";
import { languageMetadataField } from "../../language/metadata";
import { createNotebookLens } from "../lens";
import { NotebookLanguageServerClient } from "../notebook-lsp";
import { CellDocumentUri, type ILanguageServerClient } from "../types";

const Cells = {
  cell1: "cell1" as CellId,
  cell2: "cell2" as CellId,
  cell3: "cell3" as CellId,
};

describe("createNotebookLens", () => {
  it("should produce correct lens for same inputs", () => {
    // Use unique content for this test
    const cellIds: CellId[] = [Cells.cell1, Cells.cell2];
    const codes: Record<CellId, string> = {
      [Cells.cell1]: "unique_memo_test_line1",
      [Cells.cell2]: "unique_memo_test_line2",
    };

    const lens1 = createNotebookLens(cellIds, codes);
    const lens2 = createNotebookLens(cellIds, codes);

    // Same inputs should produce equivalent lens (same merged text)
    expect(lens1.mergedText).toBe(lens2.mergedText);
    expect(lens1.cellIds).toEqual(lens2.cellIds);

    // Different content should produce a different lens
    const differentCodes: Record<CellId, string> = {
      [Cells.cell1]: "unique_memo_different",
      [Cells.cell2]: "unique_memo_content",
    };
    const lens3 = createNotebookLens(cellIds, differentCodes);
    expect(lens3.mergedText).not.toBe(lens1.mergedText);
  });

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

  it("order of code should not matter", () => {
    const cellIds: CellId[] = [Cells.cell1, Cells.cell2];
    let codes: Record<CellId, string> = {
      [Cells.cell1]: "before\ntext",
      [Cells.cell2]: "cell1\ncell2",
    };
    let lens = createNotebookLens(cellIds, codes);
    expect(lens.mergedText).toBe("before\ntext\ncell1\ncell2");

    // Swap them around
    codes = {
      [Cells.cell2]: "cell1\ncell2",
      [Cells.cell1]: "before\ntext",
    };
    lens = createNotebookLens(cellIds, codes);
    expect(lens.mergedText).toBe("before\ntext\ncell1\ncell2");
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

    // This triggers the cross-cell diagnostic warning (start in range, end outside)
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

  it("should detect cross-cell diagnostics where start is in range but end is outside", () => {
    const cellIds: CellId[] = [Cells.cell1, Cells.cell2];
    const codes: Record<CellId, string> = {
      [Cells.cell1]: "line1\nline2",
      [Cells.cell2]: "line3",
    };
    const lens = createNotebookLens(cellIds, codes);

    // Range that starts in cell1 (line 1) but ends in cell2 (line 2 = first line of cell2)
    // This should return false and log a warning
    const crossCellRange = {
      start: { line: 1, character: 0 }, // line 1 is in cell1
      end: { line: 2, character: 0 }, // line 2 is in cell2
    };

    expect(lens.isInRange(crossCellRange, Cells.cell1)).toBe(false);
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
  let mockClient: Mocked<ILanguageServerClient>;
  let notebookClient: NotebookLanguageServerClient;

  beforeEach(() => {
    mockClient = {
      ready: true,
      capabilities: {},
      initializePromise: Promise.resolve(),
      clientCapabilities: {},
      completionItemResolve: vi.fn(),
      initialize: vi.fn(),
      close: vi.fn(),
      onNotification: vi.fn(),
      textDocumentDidOpen: vi.fn(),
      textDocumentDidChange: vi.fn(),
      textDocumentHover: vi.fn(),
      textDocumentCompletion: vi.fn(),
      textDocumentDefinition: vi.fn(),
      textDocumentPrepareRename: vi.fn(),
      textDocumentCodeAction: vi.fn(),
      textDocumentSignatureHelp: vi.fn(),
      textDocumentRename: vi.fn(),
    };
    (mockClient as any).processNotification = vi.fn();
    (mockClient as any).notify = vi.fn();
    notebookClient = new NotebookLanguageServerClient(mockClient, {}, () => ({
      [Cells.cell1]: new EditorView({ doc: "# this is a comment" }),
      [Cells.cell2]: new EditorView({ doc: "import math\nimport numpy" }),
      [Cells.cell3]: new EditorView({ doc: "print(math.sqrt(4))" }),
    }));

    // Mock the atom instead of the instance method
    vi.spyOn(store, "get").mockImplementation((atom) => {
      if (atom === topologicalCodesAtom) {
        return {
          cellIds: [Cells.cell1, Cells.cell2, Cells.cell3],
          codes: {
            [Cells.cell1]: "# this is a comment",
            [Cells.cell2]: "import math\nimport numpy",
            [Cells.cell3]: "print(math.sqrt(4))",
          },
        };
      }
      return undefined;
    });

    (NotebookLanguageServerClient as any).SEEN_CELL_DOCUMENT_URIS.clear();
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
        value: "test hover",
      });
    });

    it("should normalize math content in hover markdown", async () => {
      const hoverParams: LSP.HoverParams = {
        textDocument: { uri: "file:///cell1.py" },
        position: { line: 0, character: 1 },
      };

      const mockHoverResponse: LSP.Hover = {
        contents: {
          kind: "markdown",
          value:
            "For t > 0:\n\n.. math::\n\n\\begin{align*}\nm_t &= \\beta_1 \\cdot g_t\n\\end{align*}",
        },
      };

      mockClient.textDocumentHover.mockResolvedValue(mockHoverResponse);

      await notebookClient.textDocumentDidOpen({
        textDocument: {
          uri: "file:///cell1.py",
          languageId: "python",
          version: 1,
          text: "value = 1",
        },
      });

      const result = await notebookClient.textDocumentHover(hoverParams);
      const contents = result?.contents as LSP.MarkupContent;

      expect(contents.kind).toBe("markdown");
      expect(contents.value).toContain("<marimo-tex");
      expect(contents.value).not.toContain(".. math::");
      expect(contents.value).toContain("\\begin{align*}");
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

    it("should normalize completion item markdown documentation", async () => {
      const completionParams: LSP.CompletionParams = {
        textDocument: { uri: "file:///cell1.py" },
        position: { line: 0, character: 4 },
      };

      const mockCompletionResponse: LSP.CompletionList = {
        isIncomplete: false,
        items: [
          {
            label: "math_completion",
            kind: LSP.CompletionItemKind.Function,
            documentation: {
              kind: "markdown",
              value: "Compute :math:`x^2`",
            },
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
          text: "math",
        },
      });

      const result =
        await notebookClient.textDocumentCompletion(completionParams);
      const completion = (result as LSP.CompletionList).items[0];
      const documentation = completion?.documentation as LSP.MarkupContent;

      expect(documentation.kind).toBe("markdown");
      expect(documentation.value).toContain("<marimo-tex");
      expect(documentation.value).not.toContain(":math:`");
    });

    it("should normalize completion item plaintext math documentation", async () => {
      const completionParams: LSP.CompletionParams = {
        textDocument: { uri: "file:///cell1.py" },
        position: { line: 0, character: 4 },
      };

      const mockCompletionResponse: LSP.CompletionList = {
        isIncomplete: false,
        items: [
          {
            label: "math_completion_plain",
            kind: LSP.CompletionItemKind.Function,
            documentation: {
              kind: "plaintext",
              value: "For t > 0:\n\n.. math::\n\n    m_t = \\beta_1 \\cdot g_t",
            },
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
          text: "math",
        },
      });

      const result =
        await notebookClient.textDocumentCompletion(completionParams);
      const completion = (result as LSP.CompletionList).items[0];
      const documentation = completion?.documentation as LSP.MarkupContent;

      expect(documentation.kind).toBe("markdown");
      expect(documentation.value).toContain("<marimo-tex");
      expect(documentation.value).not.toContain(".. math::");
    });
  });

  describe("completionItemResolve", () => {
    it("should normalize resolved completion markdown documentation", async () => {
      const unresolvedItem: LSP.CompletionItem = { label: "test" };
      const resolvedItem: LSP.CompletionItem = {
        label: "test",
        documentation: {
          kind: "markdown",
          value: "For t > 0:\n\n.. math::\n\n    m_t = \\beta_1 \\cdot g_t",
        },
      };

      mockClient.completionItemResolve.mockResolvedValue(resolvedItem);

      const result = await notebookClient.completionItemResolve(unresolvedItem);
      const documentation = result.documentation as LSP.MarkupContent;

      expect(documentation.kind).toBe("markdown");
      expect(documentation.value).toContain("<marimo-tex");
      expect(documentation.value).not.toContain(".. math::");
    });
  });

  describe("textDocumentSignatureHelp", () => {
    it("should normalize signature and parameter markdown documentation", async () => {
      const signatureHelpParams: LSP.SignatureHelpParams = {
        textDocument: { uri: "file:///cell1.py" },
        position: { line: 0, character: 3 },
      };

      const mockSignatureHelp: LSP.SignatureHelp = {
        signatures: [
          {
            label: "foo(x)",
            documentation: {
              kind: "markdown",
              value: "Compute :math:`x^2`",
            },
            parameters: [
              {
                label: "x",
                documentation: {
                  kind: "markdown",
                  value:
                    "For t > 0:\n\n.. math::\n\n    m_t = \\beta_1 \\cdot g_t",
                },
              },
            ],
          },
        ],
      };

      mockClient.textDocumentSignatureHelp.mockResolvedValue(mockSignatureHelp);

      await notebookClient.textDocumentDidOpen({
        textDocument: {
          uri: "file:///cell1.py",
          languageId: "python",
          version: 1,
          text: "foo(",
        },
      });

      const result =
        await notebookClient.textDocumentSignatureHelp(signatureHelpParams);
      const signature = result?.signatures[0];
      const signatureDoc = signature?.documentation as LSP.MarkupContent;
      const parameterDoc = signature?.parameters?.[0]
        ?.documentation as LSP.MarkupContent;

      expect(signatureDoc.value).toContain("<marimo-tex");
      expect(signatureDoc.value).not.toContain(":math:`");
      expect(parameterDoc.value).toContain("<marimo-tex");
      expect(parameterDoc.value).not.toContain(".. math::");
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
          languageAdapterState.init(() => new PythonLanguageAdapter()),
          languageMetadataField.init(() => ({})),
          languageServerWithClient({
            client: mockClient as unknown as LanguageServerClient,
            documentUri: CellDocumentUri.of(Cells.cell1),
            ...props,
          }),
        ],
      });
      expect(mockView1.state.doc.toString()).toBe("# this is a comment");

      const mockView2 = new EditorView({
        doc: "import math\nimport numpy",
        extensions: [
          languageAdapterState.init(() => new PythonLanguageAdapter()),
          languageMetadataField.init(() => ({})),
          languageServerWithClient({
            client: mockClient as unknown as LanguageServerClient,
            documentUri: CellDocumentUri.of(Cells.cell2),
            ...props,
          }),
        ],
      });
      expect(mockView2.state.doc.toString()).toBe("import math\nimport numpy");

      const mockView3 = new EditorView({
        doc: "print(math.sqrt(4))",
        extensions: [
          languageAdapterState.init(() => new PythonLanguageAdapter()),
          languageMetadataField.init(() => ({})),
          languageServerWithClient({
            client: mockClient as unknown as LanguageServerClient,
            documentUri: CellDocumentUri.of(Cells.cell3),
            ...props,
          }),
        ],
      });
      expect(mockView3.state.doc.toString()).toBe("print(math.sqrt(4))");

      (notebookClient as any).getNotebookEditors = () => ({
        [Cells.cell1]: mockView1,
        [Cells.cell2]: mockView2,
        [Cells.cell3]: mockView3,
      });

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
                  end: { line: 3, character: 17 },
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

    it("should handle raw strings with markdown content during rename (issue #7377)", async () => {
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
      const markdownCell = 'mo.md(r"""\n# Header\n""")';
      const variableCell = "a = 'Test'";

      const mockView1 = new EditorView({
        doc: "import marimo as mo",
        extensions: [
          languageAdapterState.init(() => new PythonLanguageAdapter()),
          languageMetadataField.init(() => ({})),
          languageServerWithClient({
            client: mockClient as unknown as LanguageServerClient,
            documentUri: CellDocumentUri.of(Cells.cell1),
            ...props,
          }),
        ],
      });

      const mockView2 = new EditorView({
        doc: markdownCell,
        extensions: [
          languageAdapterState.init(() => new PythonLanguageAdapter()),
          languageMetadataField.init(() => ({})),
          languageServerWithClient({
            client: mockClient as unknown as LanguageServerClient,
            documentUri: CellDocumentUri.of(Cells.cell2),
            ...props,
          }),
        ],
      });

      const mockView3 = new EditorView({
        doc: variableCell,
        extensions: [
          languageAdapterState.init(() => new PythonLanguageAdapter()),
          languageMetadataField.init(() => ({})),
          languageServerWithClient({
            client: mockClient as unknown as LanguageServerClient,
            documentUri: CellDocumentUri.of(Cells.cell3),
            ...props,
          }),
        ],
      });

      (notebookClient as any).getNotebookEditors = () => ({
        [Cells.cell1]: mockView1,
        [Cells.cell2]: mockView2,
        [Cells.cell3]: mockView3,
      });

      // Update the mock to return the correct codes
      vi.spyOn(store, "get").mockImplementation((atom) => {
        if (atom === topologicalCodesAtom) {
          return {
            cellIds: [Cells.cell1, Cells.cell2, Cells.cell3],
            codes: {
              [Cells.cell1]: "import marimo as mo",
              [Cells.cell2]: markdownCell,
              [Cells.cell3]: variableCell,
            },
          };
        }
        return undefined;
      });

      // Setup rename params - renaming variable 'a' in cell3
      const renameParams: LSP.RenameParams = {
        textDocument: { uri: CellDocumentUri.of(Cells.cell3) },
        position: { line: 0, character: 0 }, // position of 'a'
        newName: "b",
      };

      // Open a document first to set up the lens
      await notebookClient.textDocumentDidOpen({
        textDocument: {
          uri: CellDocumentUri.of(Cells.cell3),
          languageId: "python",
          version: 1,
          text: variableCell,
        },
      });

      // Mock the response from the language server
      // The merged document includes all cells (5 lines total):
      // Line 0: "import marimo as mo"
      // Line 1: "mo.md(r\"\"\""
      // Line 2: "# Header"
      // Line 3: "\"\"\")"
      // Line 4: "a = 'Test'"
      // When renaming variable 'a' to 'b', the entire document is returned
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
                  end: { line: 4, character: 10 },
                },
                // The renamed text should preserve all cells including markdown
                newText:
                  'import marimo as mo\nmo.md(r"""\n# Header\n""")\nb = \'Test\'',
              },
            ],
          },
        ],
      };

      mockClient.textDocumentRename = vi
        .fn()
        .mockResolvedValue(mockRenameResponse);

      // Call rename
      await notebookClient.textDocumentRename(renameParams);

      // Verify that the markdown cell was NOT corrupted and remains unchanged
      expect(mockView2.state.doc.toString()).toBe(markdownCell);
      // Verify that the variable cell was renamed
      expect(mockView3.state.doc.toString()).toBe("b = 'Test'");
      // Verify that the import cell was not changed
      expect(mockView1.state.doc.toString()).toBe("import marimo as mo");
    });

    it("should only rename private variables in the current cell (issue #7810)", async () => {
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

      // Setup editor views - both cells have a private variable _x
      const cell1Code = "_x = 1\nprint(_x)";
      const cell2Code = "_x = 2\nprint(_x)";

      const mockView1 = new EditorView({
        doc: cell1Code,
        extensions: [
          languageAdapterState.init(() => new PythonLanguageAdapter()),
          languageMetadataField.init(() => ({})),
          languageServerWithClient({
            client: mockClient as unknown as LanguageServerClient,
            documentUri: CellDocumentUri.of(Cells.cell1),
            ...props,
          }),
        ],
      });

      const mockView2 = new EditorView({
        doc: cell2Code,
        extensions: [
          languageAdapterState.init(() => new PythonLanguageAdapter()),
          languageMetadataField.init(() => ({})),
          languageServerWithClient({
            client: mockClient as unknown as LanguageServerClient,
            documentUri: CellDocumentUri.of(Cells.cell2),
            ...props,
          }),
        ],
      });

      (notebookClient as any).getNotebookEditors = () => ({
        [Cells.cell1]: mockView1,
        [Cells.cell2]: mockView2,
      });

      // Update the mock to return the correct codes
      vi.spyOn(store, "get").mockImplementation((atom) => {
        if (atom === topologicalCodesAtom) {
          return {
            cellIds: [Cells.cell1, Cells.cell2],
            codes: {
              [Cells.cell1]: cell1Code,
              [Cells.cell2]: cell2Code,
            },
          };
        }
        return undefined;
      });

      // Setup rename params - renaming _x in cell1
      const renameParams: LSP.RenameParams = {
        textDocument: { uri: CellDocumentUri.of(Cells.cell1) },
        position: { line: 0, character: 0 }, // position of '_x'
        newName: "_y",
      };

      // Open a document first to set up the lens
      await notebookClient.textDocumentDidOpen({
        textDocument: {
          uri: CellDocumentUri.of(Cells.cell1),
          languageId: "python",
          version: 1,
          text: cell1Code,
        },
      });

      // Mock the response from the language server
      // The LSP server would rename _x in BOTH cells (since it sees the merged doc)
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
                  end: { line: 3, character: 10 },
                },
                // LSP renames _x to _y in both cells
                newText: "_y = 1\nprint(_y)\n_y = 2\nprint(_y)",
              },
            ],
          },
        ],
      };

      mockClient.textDocumentRename = vi
        .fn()
        .mockResolvedValue(mockRenameResponse);

      // Call rename
      await notebookClient.textDocumentRename(renameParams);

      // The fix: only cell1 should be renamed, cell2 should remain unchanged
      // because private variables are cell-local in marimo
      expect(mockView1.state.doc.toString()).toBe("_y = 1\nprint(_y)");
      expect(mockView2.state.doc.toString()).toBe("_x = 2\nprint(_x)");
    });
  });

  describe("diagnostics handling", () => {
    it("should transform diagnostic ranges and filter out-of-bounds diagnostics", async () => {
      // Mock processNotification to capture the transformed diagnostics
      const capturedDiagnostics: LSP.PublishDiagnosticsParams[] = [];
      // @ts-expect-error: processNotification is private
      mockClient.processNotification = vi
        .fn()
        .mockImplementation((notification: any) => {
          if (notification.method === "textDocument/publishDiagnostics") {
            capturedDiagnostics.push(notification.params);
          }
        });

      // Call patch since we changed processNotification
      notebookClient.patchProcessNotification();
      // Start the document version at 1
      (notebookClient as any).documentVersion = 1;

      // Open documents for multiple cells so they get tracked
      await notebookClient.textDocumentDidOpen({
        textDocument: {
          uri: CellDocumentUri.of(Cells.cell1),
          languageId: "python",
          version: 1,
          text: "import math\nimport numpy",
        },
      });

      await notebookClient.textDocumentDidOpen({
        textDocument: {
          uri: CellDocumentUri.of(Cells.cell2),
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
                start: { line: 2, character: 0 },
                end: { line: 2, character: 4 },
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

      expect(capturedDiagnostics).toHaveLength(2);
      expect(capturedDiagnostics[0].diagnostics).toHaveLength(1);
      expect(capturedDiagnostics[0].diagnostics[0].range).toEqual({
        start: { line: 1, character: 0 },
        end: { line: 1, character: 4 },
      });

      // Rest are cleared
      expect(capturedDiagnostics[1].diagnostics).toHaveLength(0);
    });

    it("should clear diagnostics for all cells when receiving empty diagnostics", async () => {
      await notebookClient.sync();

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

      // Open documents so they get tracked
      await notebookClient.textDocumentDidOpen({
        textDocument: {
          uri: CellDocumentUri.of(Cells.cell1),
          languageId: "python",
          version: 1,
          text: "import math\nimport numpy",
        },
      });

      await notebookClient.textDocumentDidOpen({
        textDocument: {
          uri: CellDocumentUri.of(Cells.cell2),
          languageId: "python",
          version: 1,
          text: "import math\nimport numpy",
        },
      });

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

      // Open documents for multiple cells so they get tracked
      await notebookClient.textDocumentDidOpen({
        textDocument: {
          uri: CellDocumentUri.of(Cells.cell1),
          languageId: "python",
          version: 1,
          text: "import math\nimport numpy",
        },
      });

      await notebookClient.textDocumentDidOpen({
        textDocument: {
          uri: CellDocumentUri.of(Cells.cell2),
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
      mockClient.textDocumentDidChange = vi
        .fn()
        .mockImplementation((params) => {
          return params;
        });

      const result = await notebookClient.textDocumentDidChange({
        textDocument: {
          uri: CellDocumentUri.of(Cells.cell1),
          version: 5,
        },
        contentChanges: [{ text: "new code" }],
      });

      expect(result).toBeDefined();
      expect(result.textDocument.version).toBeGreaterThan(0);
      expect(result.contentChanges).toHaveLength(1);
      expect(result.contentChanges[0].text).toMatchInlineSnapshot(`
        "# this is a comment
        import math
        import numpy
        print(math.sqrt(4))"
      `);
    });
  });

  describe("sync returns lens to prevent race conditions", () => {
    it("should return the lens used for synchronization", async () => {
      mockClient.textDocumentDidChange = vi
        .fn()
        .mockImplementation((params) => params);

      const result = await notebookClient.sync();

      // sync() should return both params and the lens
      expect(result).toHaveProperty("params");
      expect(result).toHaveProperty("lens");
      expect(result.lens.cellIds).toEqual([
        Cells.cell1,
        Cells.cell2,
        Cells.cell3,
      ]);
      expect(result.lens.mergedText).toContain("# this is a comment");
    });

    it("should return consistent lens even when called multiple times rapidly", async () => {
      mockClient.textDocumentDidChange = vi
        .fn()
        .mockImplementation((params) => params);

      // Call sync multiple times rapidly
      const [result1, result2, result3] = await Promise.all([
        notebookClient.sync(),
        notebookClient.sync(),
        notebookClient.sync(),
      ]);

      // All should return the same lens content (memoized)
      expect(result1.lens.mergedText).toBe(result2.lens.mergedText);
      expect(result2.lens.mergedText).toBe(result3.lens.mergedText);
    });
  });

  describe("SEEN_CELL_DOCUMENT_URIS memory management", () => {
    it("should track opened cells in SEEN_CELL_DOCUMENT_URIS", async () => {
      // Clear any existing state
      const seenUris = (NotebookLanguageServerClient as any)
        .SEEN_CELL_DOCUMENT_URIS;
      seenUris.clear();

      // Open some cells to add them to SEEN_CELL_DOCUMENT_URIS
      await notebookClient.textDocumentDidOpen({
        textDocument: {
          uri: CellDocumentUri.of(Cells.cell1),
          languageId: "python",
          version: 1,
          text: "code1",
        },
      });

      await notebookClient.textDocumentDidOpen({
        textDocument: {
          uri: CellDocumentUri.of(Cells.cell2),
          languageId: "python",
          version: 1,
          text: "code2",
        },
      });

      // Verify cells were added
      expect(seenUris.has(CellDocumentUri.of(Cells.cell1))).toBe(true);
      expect(seenUris.has(CellDocumentUri.of(Cells.cell2))).toBe(true);
      expect(seenUris.size).toBe(2);
    });

    it("should have pruneSeenCellUris static method", () => {
      // Verify the method exists and is callable
      expect(
        typeof (NotebookLanguageServerClient as any).pruneSeenCellUris,
      ).toBe("function");
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
