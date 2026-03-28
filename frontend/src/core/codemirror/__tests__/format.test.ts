/* Copyright 2026 Marimo. All rights reserved. */

import { python } from "@codemirror/lang-python";
import { EditorState } from "@codemirror/state";
import { EditorView } from "@codemirror/view";
import { atom } from "jotai";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MockRequestClient } from "@/__mocks__/requests";
import { cellId } from "@/__tests__/branded";
import type { NotebookState } from "@/core/cells/cells";
import { getNotebook } from "@/core/cells/cells";
import type { CellId } from "@/core/cells/ids";
import { notebookCellEditorViews } from "@/core/cells/utils";
import { getResolvedMarimoConfig } from "@/core/config/config";
import type { ConnectionName } from "@/core/datasets/engines";
import { OverridingHotkeyProvider } from "@/core/hotkeys/hotkeys";
import { requestClientAtom } from "@/core/network/requests";
import type { MarimoConfig } from "@/core/network/types";
import { store } from "@/core/state/jotai";
import { type CodemirrorCellActions, cellActionsState } from "../cells/state";
import { cellIdState } from "../config/extension";
import { formatAll, formatEditorViews, formatSQL } from "../format";
import {
  adaptiveLanguageConfiguration,
  switchLanguage,
} from "../language/extension";

const mockRequestClient = MockRequestClient.create();

vi.mock("@/core/cells/cells", () => ({
  getNotebook: vi.fn(),
}));

vi.mock("@/core/cells/utils", () => ({
  notebookCellEditorViews: vi.fn(),
}));

vi.mock("@/core/config/config", () => ({
  getResolvedMarimoConfig: vi.fn(),
  resolvedMarimoConfigAtom: atom({
    display: {
      theme: "light",
    },
  }),
}));

const updateCellCode = vi.fn();
const createdViews: EditorView[] = [];

function createEditor(content: string, cellId: CellId) {
  const state = EditorState.create({
    doc: content,
    extensions: [
      python(),
      adaptiveLanguageConfiguration({
        cellId,
        completionConfig: {
          activate_on_typing: true,
          signature_hint_on_typing: false,
          copilot: false,
          codeium_api_key: null,
        },
        hotkeys: new OverridingHotkeyProvider({}),
        placeholderType: "marimo-import",
        lspConfig: {},
      }),
      cellIdState.of(cellId),
      cellActionsState.of({
        updateCellCode,
      } as unknown as CodemirrorCellActions),
    ],
  });

  const view = new EditorView({
    state,
    parent: document.body,
  });

  createdViews.push(view);
  return view;
}

const mockConfig = {
  formatting: { line_length: 88 },
} as MarimoConfig;

beforeEach(() => {
  updateCellCode.mockClear();
  vi.clearAllMocks();
  // Set the mock request client in the atom
  store.set(requestClientAtom, mockRequestClient);
});

afterEach(() => {
  for (const view of createdViews) {
    view.destroy();
  }
});

describe("format", () => {
  describe("formatEditorViews", () => {
    it("should format code in editor views", async () => {
      const cid1 = cellId("1");
      const cid2 = cellId("2");
      const views = {
        [cid1]: createEditor("import numpy as    np", cid1),
        [cid2]: createEditor("import pandas as    pd", cid2),
      };

      const formattedCode1 = "import numpy as np";
      const formattedCode2 = "import pandas as pd";

      mockRequestClient.sendFormat.mockResolvedValueOnce({
        codes: {
          [cid1]: formattedCode1,
          [cid2]: formattedCode2,
        },
      });

      vi.mocked(getResolvedMarimoConfig).mockReturnValueOnce(mockConfig);

      await formatEditorViews(views);

      expect(mockRequestClient.sendFormat).toHaveBeenCalledWith({
        codes: {
          [cid1]: "import numpy as    np",
          [cid2]: "import pandas as    pd",
        },
        lineLength: 88,
      });

      expect(views[cid1].state.doc.toString()).toBe(formattedCode1);
      expect(views[cid2].state.doc.toString()).toBe(formattedCode2);
      expect(updateCellCode).toHaveBeenCalledWith({
        cellId: cid1,
        code: formattedCode1,
        formattingChange: true,
      });
      expect(updateCellCode).toHaveBeenCalledWith({
        cellId: cid2,
        code: formattedCode2,
        formattingChange: true,
      });
    });

    it("should not update editor if formatted code is same as original", async () => {
      const cid = cellId("1");
      const originalCode = "import numpy as np";
      const views = {
        [cid]: createEditor(originalCode, cid),
      };

      mockRequestClient.sendFormat.mockResolvedValueOnce({
        codes: {
          [cid]: originalCode,
        },
      });

      vi.mocked(getResolvedMarimoConfig).mockReturnValueOnce(mockConfig);

      await formatEditorViews(views);

      expect(views[cid].state.doc.toString()).toBe(originalCode);
      expect(updateCellCode).not.toHaveBeenCalled();
    });
  });

  describe("formatAll", () => {
    it("should format all cells in notebook", async () => {
      const cid1 = cellId("1");
      const cid2 = cellId("2");
      const views = {
        [cid1]: createEditor("import numpy as    np", cid1),
        [cid2]: createEditor("import pandas as    pd", cid2),
      };

      vi.mocked(getNotebook).mockReturnValueOnce({} as NotebookState);
      vi.mocked(notebookCellEditorViews).mockReturnValueOnce(views);
      mockRequestClient.sendFormat.mockResolvedValueOnce({
        codes: {
          [cid1]: "import numpy as np",
          [cid2]: "import pandas as pd",
        },
      });

      vi.mocked(getResolvedMarimoConfig).mockReturnValueOnce(mockConfig);

      await formatAll();

      expect(mockRequestClient.sendFormat).toHaveBeenCalledWith({
        codes: {
          [cid1]: "import numpy as    np",
          [cid2]: "import pandas as    pd",
        },
        lineLength: 88,
      });

      expect(updateCellCode).toHaveBeenCalledWith({
        cellId: cid1,
        code: "import numpy as np",
        formattingChange: true,
      });
    });
  });

  describe("formatSQL", () => {
    it("should format SQL code", async () => {
      const cid = cellId("1");
      const editor = createEditor("SELECT * FROM table WHERE id = 1", cid);
      switchLanguage(editor, { language: "sql" });

      await formatSQL(editor, "duckdb" as ConnectionName);

      // Check that the SQL was formatted
      expect(editor.state.doc.toString()).toMatchInlineSnapshot(`
        "SELECT
          *
        FROM
          table
        WHERE
          id = 1"
      `);
      expect(updateCellCode).toHaveBeenCalledWith({
        cellId: cid,
        code: editor.state.doc.toString(),
        formattingChange: true,
      });
    });

    it("should not format if language adapter is not SQL", async () => {
      const cid = cellId("1");
      const editor = createEditor("SELECT * FROM table WHERE id = 1", cid);
      switchLanguage(editor, { language: "python" });

      await formatSQL(editor, "duckdb" as ConnectionName);

      // Check that the SQL was not formatted
      expect(editor.state.doc.toString()).toBe(
        "SELECT * FROM table WHERE id = 1",
      );
      expect(updateCellCode).not.toHaveBeenCalled();
    });
  });

  it("should format SQL code with different dialect", async () => {
    const cid = cellId("1");
    const editor = createEditor("SELECT * FROM `table.dot` WHERE id = 1", cid);
    switchLanguage(editor, { language: "sql" });

    await formatSQL(editor, "mysql" as ConnectionName); // mysql uses backticks for identifiers

    expect(editor.state.doc.toString()).toMatchInlineSnapshot(`
      "SELECT
        *
      FROM
        \`table.dot\`
      WHERE
        id = 1"
    `);
    expect(updateCellCode).toHaveBeenCalledWith({
      cellId: cid,
      code: editor.state.doc.toString(),
      formattingChange: true,
    });
  });
});
