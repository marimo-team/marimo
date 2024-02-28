/* Copyright 2024 Marimo. All rights reserved. */
import { beforeEach, afterEach, expect, vi, describe, test } from "vitest";
import { RequestingTree } from "../requesting-tree";
import { toast } from "@/components/ui/use-toast";

const sendListFiles = vi.fn();
const sendCreateFileOrFolder = vi.fn();
const sendDeleteFileOrFolder = vi.fn();
const sendRenameFileOrFolder = vi.fn();

vi.mock("@/components/ui/use-toast", () => ({
  toast: vi.fn(),
}));

describe("RequestingTree", () => {
  let requestingTree: RequestingTree;
  const mockOnChange = vi.fn();

  beforeEach(async () => {
    requestingTree = new RequestingTree({
      listFiles: sendListFiles,
      createFileOrFolder: sendCreateFileOrFolder,
      deleteFileOrFolder: sendDeleteFileOrFolder,
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
    expect(mockOnChange.mock.calls.at(-1)[0]).toMatchInlineSnapshot(`
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
    expect(mockOnChange.mock.calls.at(-1)[0]).toMatchInlineSnapshot(`
      [
        {
          "id": "1.1",
          "name": "file2",
          "path": "/root/file2",
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
    expect(mockOnChange.mock.calls.at(-1)[0]).toMatchInlineSnapshot(`
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

  test("refreshAll should refresh data for all open folders", async () => {
    await requestingTree.refreshAll(["1.1"]);
    expect(sendListFiles).toHaveBeenCalled();
    expect(mockOnChange).toHaveBeenCalled();
    expect(mockOnChange.mock.calls.at(-1)[0]).toMatchInlineSnapshot(`
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
});
