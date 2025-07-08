/* Copyright 2024 Marimo. All rights reserved. */

import { python } from "@codemirror/lang-python";
import { EditorState } from "@codemirror/state";
import { EditorView } from "@codemirror/view";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { NotebookState } from "@/core/cells/cells";
import { getNotebook } from "@/core/cells/cells";
import type { CellId } from "@/core/cells/ids";
import { notebookCellEditorViews } from "@/core/cells/utils";
import { getResolvedMarimoConfig } from "@/core/config/config";
import { OverridingHotkeyProvider } from "@/core/hotkeys/hotkeys";
import { sendFormat } from "@/core/network/requests";
import type { MarimoConfig } from "@/core/network/types";
import { type CodemirrorCellActions, cellActionsState } from "../cells/state";
import { cellIdState } from "../config/extension";
import { formatAll, formatEditorViews, formatSQL } from "../format";
import {
  adaptiveLanguageConfiguration,
  switchLanguage,
} from "../language/extension";

vi.mock("@/core/network/requests", () => ({
  sendFormat: vi.fn(),
}));

vi.mock("@/core/cells/cells", () => ({
  getNotebook: vi.fn(),
}));

vi.mock("@/core/cells/utils", () => ({
  notebookCellEditorViews: vi.fn(),
}));

vi.mock("@/core/config/config", () => ({
  getResolvedMarimoConfig: vi.fn(),
}));

const updateCellCode = vi.fn();

function createEditor(content: string, cellId: CellId) {
  const state = EditorState.create({
    doc: content,
    extensions: [
      python(),
      adaptiveLanguageConfiguration({
        cellId,
        completionConfig: {
          activate_on_typing: true,
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

  return view;
}

const mockConfig = {
  formatting: { line_length: 88 },
} as MarimoConfig;

beforeEach(() => {
  updateCellCode.mockClear();
});

describe("format", () => {
  describe("formatEditorViews", () => {
    it("should format code in editor views", async () => {
      const cellId1 = "1" as CellId;
      const cellId2 = "2" as CellId;
      const views = {
        [cellId1]: createEditor("import numpy as    np", cellId1),
        [cellId2]: createEditor("import pandas as    pd", cellId2),
      };

      const formattedCode1 = "import numpy as np";
      const formattedCode2 = "import pandas as pd";

      vi.mocked(sendFormat).mockResolvedValueOnce({
        codes: {
          [cellId1]: formattedCode1,
          [cellId2]: formattedCode2,
        },
      });

      vi.mocked(getResolvedMarimoConfig).mockReturnValueOnce(mockConfig);

      await formatEditorViews(views);

      expect(sendFormat).toHaveBeenCalledWith({
        codes: {
          [cellId1]: "import numpy as    np",
          [cellId2]: "import pandas as    pd",
        },
        lineLength: 88,
      });

      expect(views[cellId1].state.doc.toString()).toBe(formattedCode1);
      expect(views[cellId2].state.doc.toString()).toBe(formattedCode2);
      expect(updateCellCode).toHaveBeenCalledWith({
        cellId: cellId1,
        code: formattedCode1,
        formattingChange: true,
      });
      expect(updateCellCode).toHaveBeenCalledWith({
        cellId: cellId2,
        code: formattedCode2,
        formattingChange: true,
      });
    });

    it("should not update editor if formatted code is same as original", async () => {
      const cellId = "1" as CellId;
      const originalCode = "import numpy as np";
      const views = {
        [cellId]: createEditor(originalCode, cellId),
      };

      vi.mocked(sendFormat).mockResolvedValueOnce({
        codes: {
          [cellId]: originalCode,
        },
      });

      vi.mocked(getResolvedMarimoConfig).mockReturnValueOnce(mockConfig);

      await formatEditorViews(views);

      expect(views[cellId].state.doc.toString()).toBe(originalCode);
      expect(updateCellCode).not.toHaveBeenCalled();
    });
  });

  describe("formatAll", () => {
    it("should format all cells in notebook", async () => {
      const cellId1 = "1" as CellId;
      const cellId2 = "2" as CellId;
      const views = {
        [cellId1]: createEditor("import numpy as    np", cellId1),
        [cellId2]: createEditor("import pandas as    pd", cellId2),
      };

      vi.mocked(getNotebook).mockReturnValueOnce({} as NotebookState);
      vi.mocked(notebookCellEditorViews).mockReturnValueOnce(views);
      vi.mocked(sendFormat).mockResolvedValueOnce({
        codes: {
          [cellId1]: "import numpy as np",
          [cellId2]: "import pandas as pd",
        },
      });

      vi.mocked(getResolvedMarimoConfig).mockReturnValueOnce(mockConfig);

      await formatAll();

      expect(sendFormat).toHaveBeenCalledWith({
        codes: {
          [cellId1]: "import numpy as    np",
          [cellId2]: "import pandas as    pd",
        },
        lineLength: 88,
      });

      expect(updateCellCode).toHaveBeenCalledWith({
        cellId: cellId1,
        code: "import numpy as np",
        formattingChange: true,
      });
    });
  });

  describe("formatSQL", () => {
    it("should format SQL code", async () => {
      const cellId = "1" as CellId;
      const editor = createEditor("SELECT * FROM table WHERE id = 1", cellId);
      switchLanguage(editor, { language: "sql" });

      await formatSQL(editor);

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
        cellId: cellId,
        code: editor.state.doc.toString(),
        formattingChange: true,
      });
    });

    it("should not format if language adapter is not SQL", async () => {
      const cellId = "1" as CellId;
      const editor = createEditor("SELECT * FROM table WHERE id = 1", cellId);
      switchLanguage(editor, { language: "python" });

      await formatSQL(editor);

      // Check that the SQL was not formatted
      expect(editor.state.doc.toString()).toBe(
        "SELECT * FROM table WHERE id = 1",
      );
      expect(updateCellCode).not.toHaveBeenCalled();
    });
  });
});
