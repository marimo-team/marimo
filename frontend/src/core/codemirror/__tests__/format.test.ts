/* Copyright 2026 Marimo. All rights reserved. */

import { defaultUserConfig } from "@/core/config/config-schema";

import { python } from "@codemirror/lang-python";
import { EditorState } from "@codemirror/state";
import { EditorView } from "@codemirror/view";
import { atom } from "jotai";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MockRequestClient } from "@/__mocks__/requests";
import { cellId } from "@/__tests__/branded";
import { initialNotebookState, notebookAtom } from "@/core/cells/cells";
import type { CellId } from "@/core/cells/ids";
import { createCell } from "@/core/cells/types";
import { getResolvedMarimoConfig } from "@/core/config/config";
import type { ConnectionName } from "@/core/datasets/engines";
import { OverridingHotkeyProvider } from "@/core/hotkeys/hotkeys";
import { requestClientAtom } from "@/core/network/requests";
import type { MarimoConfig } from "@/core/network/types";
import { store } from "@/core/state/jotai";
import { cellIdState } from "../config/extension";
import { formatAll, formatCells, formatSQL } from "../format";
import {
  adaptiveLanguageConfiguration,
  switchLanguage,
} from "../language/extension";

const mockRequestClient = MockRequestClient.create();

const { writtenCodes } = vi.hoisted(() => ({ writtenCodes: vi.fn() }));
vi.mock("@/core/cells/actions", async () => {
  const { atom } = await import("jotai");
  return {
    setCellCodeAtom: atom(null, (_get, _set, value) => writtenCodes(value)),
  };
});
vi.mock("@/core/config/config", () => ({
  getResolvedMarimoConfig: vi.fn(),
  resolvedMarimoConfigAtom: atom({
    display: {
      theme: "light",
    },
  }),
}));

const createdViews: EditorView[] = [];

function createEditor(content: string, cellId: CellId) {
  const state = EditorState.create({
    doc: content,
    extensions: [
      python(),
      adaptiveLanguageConfiguration({
        cellId,
        completionConfig: {
          ...defaultUserConfig().completion,
          activate_on_typing: true,
          signature_hint_on_typing: false,
          copilot: false,
        },
        hotkeys: new OverridingHotkeyProvider({}),
        placeholderType: "marimo-import",
        lspConfig: { ...defaultUserConfig().language_servers },
      }),
      cellIdState.of(cellId),
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
  describe("formatCells", () => {
    const mounted = cellId("mounted");
    const dormant = cellId("dormant");

    function setNotebook(view: EditorView) {
      store.set(notebookAtom, {
        ...initialNotebookState(),
        cellIds: [mounted, dormant],
        cellData: {
          [mounted]: createCell({ id: mounted, code: "import numpy as    np" }),
          [dormant]: createCell({
            id: dormant,
            code: "import pandas as    pd",
          }),
        },
        cellHandles: {
          [mounted]: { current: { editorView: view } },
          [dormant]: { current: { editorView: null } },
        },
      });
    }

    function formatted() {
      return {
        codes: {
          [mounted]: "import numpy as np",
          [dormant]: "import pandas as pd",
        },
      };
    }

    afterEach(() => {
      store.set(notebookAtom, initialNotebookState());
    });

    it("formats an editor in place and a cell without one through the document", async () => {
      const view = createEditor("import numpy as    np", mounted);
      setNotebook(view);
      mockRequestClient.sendFormat.mockResolvedValueOnce(formatted());
      vi.mocked(getResolvedMarimoConfig).mockReturnValueOnce(mockConfig);

      await formatCells([mounted, dormant]);

      expect(mockRequestClient.sendFormat).toHaveBeenCalledWith({
        codes: {
          [mounted]: "import numpy as    np",
          [dormant]: "import pandas as    pd",
        },
        lineLength: 88,
      });
      expect(view.state.doc.toString()).toBe("import numpy as np");
      expect(writtenCodes.mock.calls).toEqual([
        [{ cellId: dormant, code: "import pandas as pd" }],
      ]);
    });

    it("leaves cells that formatting did not change", async () => {
      const view = createEditor("import numpy as    np", mounted);
      setNotebook(view);
      mockRequestClient.sendFormat.mockResolvedValueOnce({
        codes: {
          [mounted]: "import numpy as    np",
          [dormant]: "import pandas as    pd",
        },
      });
      vi.mocked(getResolvedMarimoConfig).mockReturnValueOnce(mockConfig);

      await formatCells([mounted, dormant]);

      expect(view.state.doc.toString()).toBe("import numpy as    np");
      expect(writtenCodes).not.toHaveBeenCalled();
    });

    it("skips a cell edited while the server was formatting", async () => {
      const view = createEditor("import numpy as    np", mounted);
      setNotebook(view);
      mockRequestClient.sendFormat.mockImplementationOnce(async () => {
        const notebook = store.get(notebookAtom);
        store.set(notebookAtom, {
          ...notebook,
          cellData: {
            ...notebook.cellData,
            [dormant]: createCell({ id: dormant, code: "x = 1" }),
          },
        });
        return formatted();
      });
      vi.mocked(getResolvedMarimoConfig).mockReturnValueOnce(mockConfig);

      await formatCells([mounted, dormant]);

      expect(view.state.doc.toString()).toBe("import numpy as np");
      expect(writtenCodes).not.toHaveBeenCalled();
    });

    it("formats every cell of the notebook with formatAll", async () => {
      setNotebook(createEditor("import numpy as    np", mounted));
      mockRequestClient.sendFormat.mockResolvedValueOnce(formatted());
      vi.mocked(getResolvedMarimoConfig).mockReturnValueOnce(mockConfig);

      await formatAll();

      expect(mockRequestClient.sendFormat).toHaveBeenCalledWith({
        codes: {
          [mounted]: "import numpy as    np",
          [dormant]: "import pandas as    pd",
        },
        lineLength: 88,
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
  });
});
