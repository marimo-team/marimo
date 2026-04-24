/* Copyright 2026 Marimo. All rights reserved. */
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import { MockModules } from "@/__mocks__/common";
import { toast } from "@/components/ui/use-toast";
import type { FilePath } from "@/utils/paths";
import { RequestingTree } from "../requesting-tree";

const sendListFiles = vi.fn();
const sendCreateFileOrFolder = vi.fn();
const sendDeleteFileOrFolder = vi.fn();
const sendCopyFileOrFolder = vi.fn();
const sendRenameFileOrFolder = vi.fn();

vi.mock("@/components/ui/use-toast", () => MockModules.toast());

describe("RequestingTree", () => {
  let requestingTree: RequestingTree;
  const mockOnChange = vi.fn();

  beforeEach(async () => {
    requestingTree = new RequestingTree({
      listFiles: sendListFiles,
      createFileOrFolder: sendCreateFileOrFolder,
      deleteFileOrFolder: sendDeleteFileOrFolder,
      copyFileOrFolder: sendCopyFileOrFolder,
      renameFileOrFolder: sendRenameFileOrFolder,
    });
    sendListFiles.mockResolvedValue({
      files: [
        { id: "1.1", name: "file1", path: "/root/file1" },
        {
          id: "1.2",
          name: "folder1",
          isDirectory: true,
          path: "/root/folder1",
        },
        {
          id: "1.3",
          name: "folder2",
          isDirectory: true,
          path: "/root/folder2",
        },
      ],
      root: "/root",
    });
    await requestingTree.initialize(mockOnChange);
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  test("initialize should load files and set rootPath", async () => {
    expect(sendListFiles).toHaveBeenCalledWith({ path: "" });
    expect(mockOnChange).toHaveBeenCalledWith([
      { id: "1.1", name: "file1", path: "/root/file1" },
      { id: "1.2", name: "folder1", isDirectory: true, path: "/root/folder1" },
      { id: "1.3", name: "folder2", isDirectory: true, path: "/root/folder2" },
    ]);
  });

  test("expand should load children for a directory", async () => {
    sendListFiles.mockResolvedValue({
      files: [{ id: "2", name: "file2", path: "/roo/folder1/file2" }],
    });
    const result = await requestingTree.expand("1.2");
    expect(result).toBe(true);
    expect(sendListFiles).toHaveBeenCalledWith({ path: "/root/folder1" });
    expect(mockOnChange).toHaveBeenCalled();
    const lastCall = mockOnChange.mock.calls.at(-1);
    expect(lastCall).toBeDefined();
    expect(lastCall![0]).toMatchInlineSnapshot(`
      [
        {
          "id": "1.1",
          "name": "file1",
          "path": "/root/file1",
        },
        {
          "children": [
            {
              "id": "2",
              "name": "file2",
              "path": "/roo/folder1/file2",
            },
          ],
          "id": "1.2",
          "isDirectory": true,
          "name": "folder1",
          "path": "/root/folder1",
        },
        {
          "id": "1.3",
          "isDirectory": true,
          "name": "folder2",
          "path": "/root/folder2",
        },
      ]
    `);
  });

  test("rename should change the name and path of a file", async () => {
    sendRenameFileOrFolder.mockResolvedValue({ success: true });

    await requestingTree.rename("1.1", "file2");
    expect(sendRenameFileOrFolder).toHaveBeenCalledWith({
      path: "/root/file1",
      newPath: "/root/file2",
    });
    expect(mockOnChange).toHaveBeenCalled();
    const lastCall = mockOnChange.mock.calls.at(-1);
    expect(lastCall).toBeDefined();
    expect(lastCall![0]).toMatchInlineSnapshot(`
      [
        {
          "id": "1.1",
          "name": "file1",
          "path": "/root/file1",
        },
        {
          "id": "1.2",
          "isDirectory": true,
          "name": "folder1",
          "path": "/root/folder1",
        },
        {
          "id": "1.3",
          "isDirectory": true,
          "name": "folder2",
          "path": "/root/folder2",
        },
      ]
    `);
  });

  test("move should change the parent of a file", async () => {
    sendRenameFileOrFolder.mockResolvedValue({ success: true });

    await requestingTree.move(["1.1"], "1.2");
    expect(sendRenameFileOrFolder).toHaveBeenCalled();
    expect(mockOnChange).toHaveBeenCalled();
    const lastCall = mockOnChange.mock.calls.at(-1);
    expect(lastCall).toBeDefined();
    expect(lastCall![0]).toMatchInlineSnapshot(`
      [
        {
          "id": "1.1",
          "name": "file1",
          "path": "/root/file1",
        },
        {
          "children": [
            {
              "id": "1.1",
              "name": "file1",
              "path": "/root/folder1/file1",
            },
          ],
          "id": "1.2",
          "isDirectory": true,
          "name": "folder1",
          "path": "/root/folder1",
        },
        {
          "id": "1.3",
          "isDirectory": true,
          "name": "folder2",
          "path": "/root/folder2",
        },
      ]
    `);
  });

  test("copy should duplicate a file", async () => {
    sendCopyFileOrFolder.mockResolvedValue({ success: true });

    await requestingTree.copy("1.1", "file1_copy");
    expect(sendCopyFileOrFolder).toHaveBeenCalledWith({
      path: "/root/file1",
      newPath: "/root/file1_copy",
    });
    expect(mockOnChange).toHaveBeenCalled();
  });

  test("delete should drop a file on success", async () => {
    sendDeleteFileOrFolder.mockResolvedValue({ success: true });

    await requestingTree.delete("1.1");
    expect(sendDeleteFileOrFolder).toHaveBeenCalledWith({
      path: "/root/file1",
    });
    const lastCall = mockOnChange.mock.calls.at(-1);
    expect(lastCall?.[0].map((f: { id: string }) => f.id)).toEqual([
      "1.2",
      "1.3",
    ]);
  });

  test("createFile should create a new file", async () => {
    sendCreateFileOrFolder.mockResolvedValue({ success: true });

    await requestingTree.createFile({ name: "file3", parentId: "1.2" });
    expect(sendCreateFileOrFolder).toHaveBeenCalledWith({
      path: "/root/folder1",
      type: "file",
      name: "file3",
    });
    expect(mockOnChange).toHaveBeenCalled();
  });

  test("createFile should create a new notebook", async () => {
    sendCreateFileOrFolder.mockResolvedValue({ success: true });

    await requestingTree.createFile({
      name: "notebook1",
      parentId: "1.2",
      type: "notebook",
    });
    expect(sendCreateFileOrFolder).toHaveBeenCalledWith({
      path: "/root/folder1",
      type: "notebook",
      name: "notebook1",
    });
    expect(mockOnChange).toHaveBeenCalled();
  });

  test("createFolder should create a new folder", async () => {
    sendCreateFileOrFolder.mockResolvedValue({ success: true });

    await requestingTree.createFolder("folder3", "1.2");
    expect(sendCreateFileOrFolder).toHaveBeenCalled();
    expect(mockOnChange).toHaveBeenCalled();
  });

  test("refreshAll should refresh data for all open folders", async () => {
    await requestingTree.refreshAll(["1.1"]);
    expect(sendListFiles).toHaveBeenCalled();
    expect(mockOnChange).toHaveBeenCalled();
    const lastCall = mockOnChange.mock.calls.at(-1);
    expect(lastCall).toBeDefined();
    expect(lastCall![0]).toMatchInlineSnapshot(`
      [
        {
          "id": "1.1",
          "name": "file1",
          "path": "/root/file1",
        },
        {
          "id": "1.2",
          "isDirectory": true,
          "name": "folder1",
          "path": "/root/folder1",
        },
        {
          "id": "1.3",
          "isDirectory": true,
          "name": "folder2",
          "path": "/root/folder2",
        },
      ]
    `);
  });

  describe("when API fails", () => {
    test("initialize should handle errors gracefully", async () => {
      requestingTree = new RequestingTree({
        listFiles: sendListFiles,
        createFileOrFolder: sendCreateFileOrFolder,
        deleteFileOrFolder: sendDeleteFileOrFolder,
        copyFileOrFolder: sendCopyFileOrFolder,
        renameFileOrFolder: sendRenameFileOrFolder,
      });
      sendListFiles.mockRejectedValue(new Error("Network error"));
      await requestingTree.initialize(mockOnChange);
      expect(toast).toHaveBeenCalledWith({
        title: "Failed",
        description: expect.any(String),
      });
    });

    test("rename should handle API failure", async () => {
      sendRenameFileOrFolder.mockResolvedValue({
        success: false,
        message: "Error renaming",
      });

      await requestingTree.rename("1.1", "file2");
      expect(sendRenameFileOrFolder).toHaveBeenCalledWith({
        path: "/root/file1",
        newPath: "/root/file2",
      });
      expect(toast).toHaveBeenCalledWith({
        title: "Failed",
        description: "Error renaming",
      });
    });

    test("rename should NOT mutate the local tree on API failure", async () => {
      sendRenameFileOrFolder.mockResolvedValue({
        success: false,
        message: "Error renaming",
      });
      const changesBefore = mockOnChange.mock.calls.length;

      await requestingTree.rename("1.1", "file2");

      // No further onChange calls should fire after the failed rename, so the
      // tree stays in sync with the backend.
      expect(mockOnChange.mock.calls.length).toBe(changesBefore);
    });

    test("delete should NOT drop the node on API failure", async () => {
      sendDeleteFileOrFolder.mockResolvedValue({
        success: false,
        message: "Error deleting",
      });
      const changesBefore = mockOnChange.mock.calls.length;

      await requestingTree.delete("1.1");
      expect(sendDeleteFileOrFolder).toHaveBeenCalledWith({
        path: "/root/file1",
      });
      expect(toast).toHaveBeenCalledWith({
        title: "Failed",
        description: "Error deleting",
      });
      expect(mockOnChange.mock.calls.length).toBe(changesBefore);
    });

    test("move should NOT mutate the local tree when rename fails", async () => {
      sendRenameFileOrFolder.mockResolvedValue({
        success: false,
        message: "Error moving",
      });

      await requestingTree.move(["1.1"], "1.2");

      expect(toast).toHaveBeenCalledWith({
        title: "Failed",
        description: "Error moving",
      });
      // The last emitted state should still have file1 at the top level, not
      // moved under folder1.
      const lastCall = mockOnChange.mock.calls.at(-1);
      expect(lastCall?.[0]).toEqual([
        { id: "1.1", name: "file1", path: "/root/file1" },
        {
          id: "1.2",
          name: "folder1",
          isDirectory: true,
          path: "/root/folder1",
        },
        {
          id: "1.3",
          name: "folder2",
          isDirectory: true,
          path: "/root/folder2",
        },
      ]);
    });

    test("copy should handle API failure", async () => {
      sendCopyFileOrFolder.mockResolvedValue({
        success: false,
        message: "Error duplicating",
      });

      await requestingTree.copy("1.1", "file1_copy");
      expect(sendCopyFileOrFolder).toHaveBeenCalledWith({
        path: "/root/file1",
        newPath: "/root/file1_copy",
      });
      expect(toast).toHaveBeenCalledWith({
        title: "Failed",
        description: "Error duplicating",
      });
    });

    test("move should handle missing parent node gracefully", async () => {
      await requestingTree.move(["1.x"], "2");
      expect(sendRenameFileOrFolder).not.toHaveBeenCalled();
      expect(mockOnChange).toHaveBeenCalledTimes(3);
    });

    test("refreshAll should handle API errors without crashing", async () => {
      sendListFiles.mockRejectedValue(new Error("Network error"));
      await requestingTree.refreshAll(["1.2"]);
      expect(sendListFiles).toHaveBeenCalled();
      // Ensure onChange is still called to update UI even if data might not have changed
      expect(mockOnChange).toHaveBeenCalled();
    });
  });

  describe("relativeFromRoot", () => {
    test("should return relative path for Unix paths", async () => {
      const tree = new RequestingTree({
        listFiles: sendListFiles,
        createFileOrFolder: sendCreateFileOrFolder,
        deleteFileOrFolder: sendDeleteFileOrFolder,
        copyFileOrFolder: sendCopyFileOrFolder,
        renameFileOrFolder: sendRenameFileOrFolder,
      });

      sendListFiles.mockResolvedValue({
        files: [],
        root: "/home/user/project",
      });

      await tree.initialize(vi.fn());

      const relativePath = tree.relativeFromRoot(
        "/home/user/project/src/file.py" as FilePath,
      );
      expect(relativePath).toBe("src/file.py");
    });

    test("should return relative path for Windows paths", async () => {
      const tree = new RequestingTree({
        listFiles: sendListFiles,
        createFileOrFolder: sendCreateFileOrFolder,
        deleteFileOrFolder: sendDeleteFileOrFolder,
        copyFileOrFolder: sendCopyFileOrFolder,
        renameFileOrFolder: sendRenameFileOrFolder,
      });

      sendListFiles.mockResolvedValue({
        files: [],
        root: "C:\\Users\\test\\project",
      });

      await tree.initialize(vi.fn());

      const relativePath = tree.relativeFromRoot(
        "C:\\Users\\test\\project\\src\\file.py" as FilePath,
      );
      expect(relativePath).toBe("src\\file.py");
    });

    test("should return original path when not under root", async () => {
      const relativePath = requestingTree.relativeFromRoot(
        "/other/path/file.py" as FilePath,
      );
      expect(relativePath).toBe("/other/path/file.py");
    });

    test("should handle root path exactly", async () => {
      const relativePath = requestingTree.relativeFromRoot("/root" as FilePath);
      expect(relativePath).toBe("/root");
    });
  });
});
