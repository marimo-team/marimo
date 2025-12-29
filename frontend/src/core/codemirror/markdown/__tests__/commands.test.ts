/* Copyright 2026 Marimo. All rights reserved. */
import { basicSetup, EditorState, EditorView } from "@uiw/react-codemirror";
import {
  afterAll,
  afterEach,
  beforeEach,
  describe,
  expect,
  test,
  vi,
} from "vitest";
import { MockRequestClient } from "@/__mocks__/requests";
import { requestClientAtom } from "@/core/network/requests";
import { filenameAtom } from "@/core/saving/file-state";
import { store } from "@/core/state/jotai";
import {
  insertBlockquote,
  insertBoldMarker,
  insertCodeMarker,
  insertImage,
  insertItalicMarker,
  insertLink,
  insertOL,
  insertTextFile,
  insertUL,
} from "../commands";

vi.mock("@/components/ui/use-toast", () => ({
  toast: vi.fn(),
}));

import { toast } from "@/components/ui/use-toast";

function createEditor(content: string) {
  const state = EditorState.create({
    doc: content,
    extensions: [basicSetup()],
  });

  const view = new EditorView({
    state,
    parent: document.body,
  });

  return view;
}

let view: EditorView | null = null;

afterEach(() => {
  if (view) {
    view.destroy();
    view = null;
  }
});

describe("insertBlockquote", () => {
  test("adds to selected lines", () => {
    view = createEditor("line 1\nline 2\nline 3");
    view.dispatch({
      selection: { anchor: 0, head: view.state.doc.length },
    });

    insertBlockquote(view);

    expect(view.state.doc.toString()).toBe("> line 1\n> line 2\n> line 3");
  });

  test("removes from selected lines", () => {
    view = createEditor("> line 1\n> line 2\n> line 3");
    view.dispatch({
      selection: { anchor: 0, head: view.state.doc.length },
    });

    insertBlockquote(view);

    expect(view.state.doc.toString()).toBe("line 1\nline 2\nline 3");
  });

  test("toggles on mixed lines", () => {
    view = createEditor("> line 1\nline 2\n> line 3");
    view.dispatch({
      selection: { anchor: 0, head: view.state.doc.length },
    });

    insertBlockquote(view);

    expect(view.state.doc.toString()).toBe("> line 1\n> line 2\n> line 3");
  });
});

describe("insertUL", () => {
  test("adds to selected lines", () => {
    view = createEditor("line 1\nline 2\nline 3");
    view.dispatch({
      selection: { anchor: 0, head: view.state.doc.length },
    });

    insertUL(view);

    expect(view.state.doc.toString()).toBe("- line 1\n- line 2\n- line 3");
  });

  test("removes from selected lines", () => {
    view = createEditor("- line 1\n- line 2\n- line 3");
    view.dispatch({
      selection: { anchor: 0, head: view.state.doc.length },
    });

    insertUL(view);

    expect(view.state.doc.toString()).toBe("line 1\nline 2\nline 3");
  });

  test("toggles on mixed lines", () => {
    view = createEditor("- line 1\nline 2\n- line 3");
    view.dispatch({
      selection: { anchor: 0, head: view.state.doc.length },
    });

    insertUL(view);

    expect(view.state.doc.toString()).toBe("- line 1\n- line 2\n- line 3");
  });
});

describe("insertOL", () => {
  test("adds to selected lines", () => {
    view = createEditor("line 1\nline 2\nline 3");
    view.dispatch({
      selection: { anchor: 0, head: view.state.doc.length },
    });

    insertOL(view);

    expect(view.state.doc.toString()).toBe("1. line 1\n1. line 2\n1. line 3");
  });

  test("removes from selected lines", () => {
    view = createEditor("1. line 1\n1. line 2\n1. line 3");
    view.dispatch({
      selection: { anchor: 0, head: view.state.doc.length },
    });

    insertOL(view);

    expect(view.state.doc.toString()).toBe("line 1\nline 2\nline 3");
  });

  test("toggles on mixed lines", () => {
    view = createEditor("1. line 1\nline 2\n1. line 3");
    view.dispatch({
      selection: { anchor: 0, head: view.state.doc.length },
    });

    insertOL(view);

    expect(view.state.doc.toString()).toBe("1. line 1\n1. line 2\n1. line 3");
  });
});

describe("insertLink", () => {
  test("inserts link at cursor position with selected text", () => {
    view = createEditor("Hello, world!");
    view.dispatch({
      selection: { anchor: 7, head: 12 },
    });

    insertLink(view);

    expect(view.state.doc.toString()).toBe("Hello, [world](http://)!");
  });
});

const mockRequestClient = MockRequestClient.create({
  sendCreateFileOrFolder: vi.fn().mockResolvedValue({
    success: true,
    info: { path: "hello.png" },
  }),
});

describe("insertImage", () => {
  const mockPngFile = () => {
    const png = new Uint8Array([1, 2, 3]);
    return new File([png], "hello.png", { type: "image/png" });
  };

  beforeEach(() => {
    vi.resetAllMocks();
    store.set(requestClientAtom, mockRequestClient);
    vi.spyOn(window, "prompt").mockImplementation(() => "hello.png");
  });

  afterAll(() => {
    vi.restoreAllMocks();
  });

  test("inserts image at cursor position", async () => {
    view = createEditor("Hello, world!");
    view.dispatch({
      selection: { anchor: 7, head: 7 },
    });

    await insertImage(view, mockPngFile());

    expect(view.state.doc.toString()).toMatchInlineSnapshot(
      `"Hello, ![alt](data:image/png;base64,AQID)world!"`,
    );
  });

  test("inserts image at cursor position with selected text", async () => {
    view = createEditor("Hello, world!");
    view.dispatch({
      selection: { anchor: 7, head: 13 },
    });

    await insertImage(view, mockPngFile());

    expect(view.state.doc.toString()).toMatchInlineSnapshot(
      `"Hello, ![world!](data:image/png;base64,AQID)"`,
    );
  });

  test("saves image as file when server request succeeds", async () => {
    view = createEditor("Hello, world!");
    view.dispatch({
      selection: { anchor: 7, head: 7 },
    });

    mockRequestClient.sendCreateFileOrFolder.mockResolvedValueOnce({
      success: true,
      info: {
        path: "public/hello.png",
        name: "hello.png",
        isMarimoFile: true,
        isDirectory: false,
        lastModified: null,
        children: [],
        id: "",
      },
    });

    await insertImage(view, mockPngFile());

    expect(mockRequestClient.sendCreateFileOrFolder).toHaveBeenCalledTimes(1);
    expect(mockRequestClient.sendCreateFileOrFolder).toHaveBeenCalledWith({
      path: "public",
      type: "file",
      name: "hello.png",
      contents: "AQID",
    });

    expect(view.state.doc.toString()).toMatchInlineSnapshot(
      `"Hello, ![alt](public/hello.png)world!"`,
    );
  });

  test("saves image in public folder of notebook directory", async () => {
    view = createEditor("Hello, world!");
    view.dispatch({
      selection: { anchor: 7, head: 7 },
    });

    // mock filenameAtom
    vi.spyOn(store, "get").mockImplementation((atom) => {
      if (atom === filenameAtom) {
        return "nested/hello.py";
      }
      if (atom === requestClientAtom) {
        return mockRequestClient;
      }
    });

    mockRequestClient.sendCreateFileOrFolder.mockResolvedValueOnce({
      success: true,
      message: null,
      info: {
        path: "nested/public/hello.png",
        name: "hello.png",
        children: [],
        id: "",
        isDirectory: false,
        isMarimoFile: true,
        lastModified: null,
      },
    });

    await insertImage(view, mockPngFile());

    expect(mockRequestClient.sendCreateFileOrFolder).toHaveBeenCalledTimes(1);
    expect(mockRequestClient.sendCreateFileOrFolder).toHaveBeenCalledWith({
      path: "nested/public", // store in public folder of notebook directory
      type: "file",
      name: "hello.png",
      contents: "AQID",
    });

    expect(view.state.doc.toString()).toMatchInlineSnapshot(
      `"Hello, ![alt](public/hello.png)world!"`,
    );
  });

  test("converts absolute path to relative path for image URL", async () => {
    view = createEditor("Hello, world!");
    view.dispatch({
      selection: { anchor: 7, head: 7 },
    });

    // mock filenameAtom with absolute path
    vi.spyOn(store, "get").mockImplementation((atom) => {
      if (atom === filenameAtom) {
        return "/Users/user/Development/project/notebook.py";
      }
      if (atom === requestClientAtom) {
        return mockRequestClient;
      }
    });

    // Server returns absolute path
    mockRequestClient.sendCreateFileOrFolder.mockResolvedValueOnce({
      success: true,
      message: null,
      info: {
        path: "/Users/user/Development/project/public/hello.png",
        name: "hello.png",
        children: [],
        id: "",
        isDirectory: false,
        isMarimoFile: false,
        lastModified: null,
      },
    });

    await insertImage(view, mockPngFile());

    expect(mockRequestClient.sendCreateFileOrFolder).toHaveBeenCalledTimes(1);
    expect(mockRequestClient.sendCreateFileOrFolder).toHaveBeenCalledWith({
      path: "/Users/user/Development/project/public",
      type: "file",
      name: "hello.png",
      contents: "AQID",
    });

    // Should convert absolute path to relative path
    expect(view.state.doc.toString()).toMatchInlineSnapshot(
      `"Hello, ![alt](public/hello.png)world!"`,
    );
  });

  test("converts absolute path to relative path in nested directory", async () => {
    view = createEditor("Hello, world!");
    view.dispatch({
      selection: { anchor: 7, head: 7 },
    });

    // mock filenameAtom with absolute path in nested directory
    vi.spyOn(store, "get").mockImplementation((atom) => {
      if (atom === filenameAtom) {
        return "/Users/user/Development/project/wip/notebook.py";
      }
      if (atom === requestClientAtom) {
        return mockRequestClient;
      }
    });

    // Server returns absolute path
    mockRequestClient.sendCreateFileOrFolder.mockResolvedValueOnce({
      success: true,
      message: null,
      info: {
        path: "/Users/user/Development/project/wip/public/image.png",
        name: "image.png",
        children: [],
        id: "",
        isDirectory: false,
        isMarimoFile: false,
        lastModified: null,
      },
    });

    await insertImage(view, mockPngFile());

    // Should convert absolute path to relative path
    expect(view.state.doc.toString()).toMatchInlineSnapshot(
      `"Hello, ![alt](public/image.png)world!"`,
    );
  });

  test("saves image as file different extension", async () => {
    view = createEditor("Hello, world!");
    view.dispatch({
      selection: { anchor: 7, head: 7 },
    });

    mockRequestClient.sendCreateFileOrFolder.mockResolvedValueOnce({
      success: true,
      info: {
        path: "public/hello.jpg",
        name: "hello.jpg",
        children: [],
        id: "",
        isDirectory: false,
        isMarimoFile: false,
      },
    });

    const mockJpgFile = () => {
      const jpg = new Uint8Array([1, 2, 3]);
      return new File([jpg], "hello.jpg", { type: "image/jpeg" });
    };

    await insertImage(view, mockJpgFile());

    expect(mockRequestClient.sendCreateFileOrFolder).toHaveBeenCalledTimes(1);
    expect(view.state.doc.toString()).toMatchInlineSnapshot(
      `"Hello, ![alt](public/hello.jpg)world!"`,
    );
  });

  test("falls back to base64 when file creation fails", async () => {
    view = createEditor("Hello, world!");
    view.dispatch({
      selection: { anchor: 7, head: 7 },
    });

    mockRequestClient.sendCreateFileOrFolder.mockResolvedValueOnce({
      success: false,
      message: "Failed to create file",
    });

    await insertImage(view, mockPngFile());

    expect(mockRequestClient.sendCreateFileOrFolder).toHaveBeenCalledTimes(1);
    expect(view.state.doc.toString()).toMatchInlineSnapshot(
      `"Hello, ![alt](data:image/png;base64,AQID)world!"`,
    );
  });

  test("rejects large files when user cancels prompt", async () => {
    view = createEditor("Hello, world!");
    view.dispatch({
      selection: { anchor: 7, head: 7 },
    });

    // User cancels the prompt
    vi.spyOn(window, "prompt").mockImplementation(() => null);

    // Create a large file (> 100KB when base64 encoded)
    // 100KB base64 = ~75KB binary, so we create 80KB to be safe
    const largeData = new Uint8Array(80 * 1024);
    const largeFile = new File([largeData], "large.png", { type: "image/png" });

    await insertImage(view, largeFile);

    // Should not insert anything
    expect(view.state.doc.toString()).toBe("Hello, world!");

    // Should show a toast about content being too large
    expect(toast).toHaveBeenCalledWith(
      expect.objectContaining({
        title: "Content too large",
      }),
    );
  });

  test("inserts small base64 when user cancels prompt", async () => {
    view = createEditor("Hello, world!");
    view.dispatch({
      selection: { anchor: 7, head: 7 },
    });

    // User cancels the prompt
    vi.spyOn(window, "prompt").mockImplementation(() => null);

    // Small file (3 bytes) - well under 100KB limit
    await insertImage(view, mockPngFile());

    // Should insert the base64 since it's small
    expect(view.state.doc.toString()).toMatchInlineSnapshot(
      `"Hello, ![alt](data:image/png;base64,AQID)world!"`,
    );
  });
});

describe("insertTextFile", () => {
  test("inserts text file at cursor position", async () => {
    view = createEditor("Hello, world!");
    view.dispatch({
      selection: { anchor: 7, head: 7 },
    });

    await insertTextFile(
      view,
      new File(["csvcsvcsv"], "my.csv", { type: "text/csv" }),
    );

    expect(view.state.doc.toString()).toMatchInlineSnapshot(
      `"Hello, csvcsvcsvworld!"`,
    );
  });

  test("inserts text file at cursor position with selected text", async () => {
    view = createEditor("Hello, world!");
    view.dispatch({
      selection: { anchor: 7, head: 13 },
    });

    await insertTextFile(
      view,
      new File(["csvcsvcsv"], "my.csv", { type: "text/csv" }),
    );

    expect(view.state.doc.toString()).toMatchInlineSnapshot(
      `"Hello, csvcsvcsvworld!"`,
    );
  });
});

describe("insertBoldMarker", () => {
  test("do not insert bold marker at cursor position", () => {
    view = createEditor("Hello, world!");
    view.dispatch({
      selection: { anchor: 7, head: 7 },
    });

    insertBoldMarker(view);

    expect(view.state.doc.toString()).toBe("Hello, world!");
  });

  test("inserts bold marker at cursor position with selected text", () => {
    view = createEditor("Hello, world!");
    view.dispatch({
      selection: { anchor: 7, head: 13 },
    });

    insertBoldMarker(view);

    expect(view.state.doc.toString()).toBe("Hello, **world!**");
  });

  test("undo bold marker at cursor position with selected text", () => {
    view = createEditor("Hello, **world!**");
    view.dispatch({
      selection: { anchor: 9, head: 15 },
    });

    insertBoldMarker(view);

    expect(view.state.doc.toString()).toBe("Hello, world!");
  });
});

describe("insertItalicMarker", () => {
  test("inserts italic marker at cursor position", () => {
    view = createEditor("Hello, world!");
    view.dispatch({
      selection: { anchor: 7, head: 7 },
    });

    insertItalicMarker(view);

    expect(view.state.doc.toString()).toBe("Hello, _world_!");
  });

  test("inserts italic marker at cursor position with selected text", () => {
    view = createEditor("Hello, world!");
    view.dispatch({
      selection: { anchor: 7, head: 13 },
    });

    insertItalicMarker(view);

    expect(view.state.doc.toString()).toBe("Hello, _world!_");
  });

  test("undo italic marker at cursor position with selected text", () => {
    view = createEditor("Hello, _world!_");
    view.dispatch({
      selection: { anchor: 8, head: 14 },
    });

    insertItalicMarker(view);

    expect(view.state.doc.toString()).toBe("Hello, world!");
  });
});

describe("insertCodeMarker", () => {
  test("inserts code marker at cursor position", () => {
    view = createEditor("Hello, world!");
    view.dispatch({
      selection: { anchor: 7, head: 7 },
    });

    insertCodeMarker(view);

    expect(view.state.doc.toString()).toMatchInlineSnapshot(`"Hello, world!"`);
  });

  test("inserts code marker at cursor position with selected text", () => {
    view = createEditor("Hello, world!");
    view.dispatch({
      selection: { anchor: 7, head: 13 },
    });

    insertCodeMarker(view);

    expect(view.state.doc.toString()).toMatchInlineSnapshot(
      `"Hello, \`world!\`"`,
    );
  });

  test("undo code marker at cursor position with selected text", () => {
    view = createEditor("Hello, `world!`");
    view.dispatch({
      selection: { anchor: 8, head: 14 },
    });

    insertCodeMarker(view);

    expect(view.state.doc.toString()).toMatchInlineSnapshot(`"Hello, world!"`);
  });

  test("inserts code marker with multiline selection", () => {
    view = createEditor(
      "Here is the python code:\nprint('Hello, world!')\n(1 + 2) * 3",
    );
    view.dispatch({
      selection: { anchor: 25, head: view.state.doc.length },
    });

    insertCodeMarker(view);

    expect(view.state.doc.toString()).toMatchInlineSnapshot(`
      "Here is the python code:
      \`\`\`
      print('Hello, world!')
      (1 + 2) * 3
      \`\`\`"
    `);
  });

  test("undo code marker with multiline selection", () => {
    view = createEditor(
      "Here is the python code:\n```\nprint('Hello, world!')\n(1 + 2) * 3\n```",
    );
    view.dispatch({
      selection: { anchor: 29, head: view.state.doc.length - 4 },
    });

    insertCodeMarker(view);

    expect(view.state.doc.toString()).toMatchInlineSnapshot(`
      "Here is the python code:
      print('Hello, world!')
      (1 + 2) * 3"
    `);
  });
});
