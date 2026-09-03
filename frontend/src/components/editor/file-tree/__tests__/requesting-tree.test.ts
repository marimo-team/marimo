/* Copyright 2026 Marimo. All rights reserved. */
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import { MockModules } from "@/__mocks__/common";
import { toast } from "@/components/ui/use-toast";
import type { FilePath } from "@/utils/paths";
import { fileTreeNodeId, RequestingTree } from "../requesting-tree";

const getRoots = vi.fn();
const sendListFiles = vi.fn();
const sendCreateFileOrFolder = vi.fn();
const sendDeleteFileOrFolder = vi.fn();
const sendCopyFileOrFolder = vi.fn();
const sendRenameFileOrFolder = vi.fn();

vi.mock("@/components/ui/use-toast", () => MockModules.toast());

const PRIMARY_FILES = [
  {
    id: "/root/file1",
    name: "file1",
    path: "/root/file1",
    isDirectory: false,
    isMarimoFile: false,
    children: [],
  },
  {
    id: "/root/folder1",
    name: "folder1",
    path: "/root/folder1",
    isDirectory: true,
    isMarimoFile: false,
    children: [],
  },
];

const PRIMARY_ROOT_ID = fileTreeNodeId("/root", "/root");
const PRIMARY_FILE_ID = fileTreeNodeId("/root", "/root/file1");
const EXTERNAL_ROOT_ID = fileTreeNodeId("/external", "/external");

describe("RequestingTree", () => {
  let tree: RequestingTree;
  const onChange = vi.fn();

  beforeEach(async () => {
    getRoots.mockResolvedValue({
      roots: [
        { path: "/root", name: "workspace", isPrimary: true },
        { path: "/external", name: "Shared", isPrimary: false },
      ],
    });
    sendListFiles.mockImplementation(async ({ path }: { path: string }) => ({
      files: path === "/root" ? PRIMARY_FILES : [],
      root: path,
    }));
    sendCreateFileOrFolder.mockResolvedValue({ success: true });
    sendDeleteFileOrFolder.mockResolvedValue({ success: true });
    sendCopyFileOrFolder.mockResolvedValue({ success: true });
    sendRenameFileOrFolder.mockResolvedValue({ success: true });

    tree = new RequestingTree({
      getRoots,
      listFiles: sendListFiles,
      createFileOrFolder: sendCreateFileOrFolder,
      deleteFileOrFolder: sendDeleteFileOrFolder,
      copyFileOrFolder: sendCopyFileOrFolder,
      renameFileOrFolder: sendRenameFileOrFolder,
    });
    await tree.initialize(onChange);
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  test("initializes with visible, unloaded root nodes", () => {
    expect(getRoots).toHaveBeenCalledOnce();
    expect(sendListFiles).not.toHaveBeenCalled();
    expect(tree.getPrimaryRootPath()).toBe("/root");
    expect(onChange).toHaveBeenLastCalledWith([
      expect.objectContaining({
        id: PRIMARY_ROOT_ID,
        name: "workspace",
        isRoot: true,
        rootId: PRIMARY_ROOT_ID,
        children: [],
      }),
      expect.objectContaining({
        id: EXTERNAL_ROOT_ID,
        name: "Shared",
        isRoot: true,
        rootId: EXTERNAL_ROOT_ID,
        children: [],
      }),
    ]);
  });

  test("flattens the primary root when there are no additional roots", async () => {
    getRoots.mockResolvedValueOnce({
      roots: [{ path: "/root", name: "workspace", isPrimary: true }],
    });
    const singleRootOnChange = vi.fn();
    const singleRootTree = new RequestingTree({
      getRoots,
      listFiles: sendListFiles,
      createFileOrFolder: sendCreateFileOrFolder,
      deleteFileOrFolder: sendDeleteFileOrFolder,
      copyFileOrFolder: sendCopyFileOrFolder,
      renameFileOrFolder: sendRenameFileOrFolder,
    });

    await singleRootTree.initialize(singleRootOnChange);

    expect(sendListFiles).toHaveBeenCalledWith({ path: "/root" });
    expect(singleRootOnChange).toHaveBeenLastCalledWith([
      expect.objectContaining({
        id: PRIMARY_FILE_ID,
        path: "/root/file1",
        isRoot: false,
        rootId: PRIMARY_ROOT_ID,
      }),
      expect.objectContaining({
        id: fileTreeNodeId("/root", "/root/folder1"),
        path: "/root/folder1",
        isRoot: false,
        rootId: PRIMARY_ROOT_ID,
      }),
    ]);

    await singleRootTree.createFile({ name: "new.txt", parentId: null });
    expect(sendCreateFileOrFolder).toHaveBeenCalledWith({
      path: "/root",
      type: "file",
      name: "new.txt",
    });
  });

  test("retries initialization without retaining partial state", async () => {
    getRoots.mockResolvedValue({
      roots: [{ path: "/root", name: "workspace", isPrimary: true }],
    });
    sendListFiles.mockRejectedValueOnce(new Error("Network error"));
    const retryOnChange = vi.fn();
    const retryTree = new RequestingTree({
      getRoots,
      listFiles: sendListFiles,
      createFileOrFolder: sendCreateFileOrFolder,
      deleteFileOrFolder: sendDeleteFileOrFolder,
      copyFileOrFolder: sendCopyFileOrFolder,
      renameFileOrFolder: sendRenameFileOrFolder,
    });

    await expect(retryTree.initialize(retryOnChange)).rejects.toThrow(
      "Network error",
    );
    expect(retryOnChange).not.toHaveBeenCalled();

    await retryTree.initialize(retryOnChange);

    expect(getRoots).toHaveBeenCalledTimes(3);
    expect(retryOnChange).toHaveBeenLastCalledWith(
      expect.arrayContaining([
        expect.objectContaining({ path: "/root/file1" }),
      ]),
    );
  });

  test("expands each root lazily and annotates its descendants", async () => {
    sendListFiles.mockResolvedValueOnce({
      files: [
        {
          id: "/external/data.csv",
          path: "/external/data.csv",
          name: "data.csv",
          isDirectory: false,
          isMarimoFile: false,
          children: [],
        },
      ],
      root: "/external",
    });

    expect(await tree.expand(EXTERNAL_ROOT_ID)).toBe(true);
    expect(sendListFiles).toHaveBeenCalledWith({ path: "/external" });
    expect(onChange.mock.calls.at(-1)?.[0][1].children[0]).toEqual(
      expect.objectContaining({
        path: "/external/data.csv",
        rootId: EXTERNAL_ROOT_ID,
        isRoot: false,
      }),
    );
  });

  test("uses the primary root for toolbar creation without a selection", async () => {
    await tree.createFile({ name: "new.txt", parentId: null });
    expect(sendCreateFileOrFolder).toHaveBeenCalledWith({
      path: "/root",
      type: "file",
      name: "new.txt",
    });
  });

  test("creates and uploads into an explicitly selected root", async () => {
    await tree.createFolder("exports", EXTERNAL_ROOT_ID);
    expect(sendCreateFileOrFolder).toHaveBeenCalledWith({
      path: "/external",
      type: "directory",
      name: "exports",
    });
  });

  test("prevents mutations of structural root nodes", async () => {
    await tree.rename(EXTERNAL_ROOT_ID, "renamed");
    await tree.copy(EXTERNAL_ROOT_ID, "copy");
    await tree.delete(EXTERNAL_ROOT_ID);

    expect(sendRenameFileOrFolder).not.toHaveBeenCalled();
    expect(sendCopyFileOrFolder).not.toHaveBeenCalled();
    expect(sendDeleteFileOrFolder).not.toHaveBeenCalled();
    expect(toast).toHaveBeenCalledWith(
      expect.objectContaining({
        description:
          "File browser roots and their parent folders cannot be modified",
      }),
    );
  });

  test("prevents mutations of configured-root ancestors", async () => {
    getRoots.mockResolvedValueOnce({
      roots: [
        { path: "/repo", name: "repo", isPrimary: true },
        {
          path: "/repo/projects/shared",
          name: "Shared",
          isPrimary: false,
        },
        { path: "/target", name: "Target", isPrimary: false },
      ],
    });
    sendListFiles.mockImplementation(async ({ path }: { path: string }) => ({
      root: path,
      files:
        path === "/repo"
          ? [
              {
                id: "/repo/projects",
                name: "projects",
                path: "/repo/projects",
                isDirectory: true,
                isMarimoFile: false,
                children: [],
              },
            ]
          : [],
    }));
    const protectedTree = new RequestingTree({
      getRoots,
      listFiles: sendListFiles,
      createFileOrFolder: sendCreateFileOrFolder,
      deleteFileOrFolder: sendDeleteFileOrFolder,
      copyFileOrFolder: sendCopyFileOrFolder,
      renameFileOrFolder: sendRenameFileOrFolder,
    });
    const primaryRootId = fileTreeNodeId("/repo", "/repo");
    const projectsId = fileTreeNodeId("/repo", "/repo/projects");
    const targetRootId = fileTreeNodeId("/target", "/target");
    await protectedTree.initialize(vi.fn());
    await protectedTree.expand(primaryRootId);

    await protectedTree.rename(projectsId, "renamed");
    await protectedTree.copy(projectsId, "projects-copy");
    await protectedTree.delete(projectsId);
    await protectedTree.move([projectsId], targetRootId);

    expect(sendRenameFileOrFolder).not.toHaveBeenCalled();
    expect(sendCopyFileOrFolder).not.toHaveBeenCalled();
    expect(sendDeleteFileOrFolder).not.toHaveBeenCalled();
  });

  test("supports copying, renaming, and deleting files by absolute path", async () => {
    await tree.expand(PRIMARY_ROOT_ID);

    await tree.copy(PRIMARY_FILE_ID, "file1_copy");
    expect(sendCopyFileOrFolder).toHaveBeenCalledWith({
      path: "/root/file1",
      newPath: "/root/file1_copy",
    });

    await tree.rename(PRIMARY_FILE_ID, "file2");
    expect(sendRenameFileOrFolder).toHaveBeenCalledWith({
      path: "/root/file1",
      newPath: "/root/file2",
    });

    await tree.delete(PRIMARY_FILE_ID);
    expect(sendDeleteFileOrFolder).toHaveBeenCalledWith({
      path: "/root/file1",
    });
  });

  describe("failed mutations", () => {
    beforeEach(async () => {
      await tree.expand(PRIMARY_ROOT_ID);
      sendListFiles.mockClear();
      onChange.mockClear();
    });

    test("does not update or refresh after a failed copy", async () => {
      sendCopyFileOrFolder.mockResolvedValueOnce({
        success: false,
        message: "Permission denied",
      });

      await tree.copy(PRIMARY_FILE_ID, "file1_copy");

      expect(sendListFiles).not.toHaveBeenCalled();
      expect(onChange).not.toHaveBeenCalled();
      expect(toast).toHaveBeenCalledWith({
        title: "Failed",
        description: "Permission denied",
      });
    });

    test("does not update or refresh after a failed rename", async () => {
      sendRenameFileOrFolder.mockResolvedValueOnce({
        success: false,
        message: "Permission denied",
      });

      await tree.rename(PRIMARY_FILE_ID, "file2");

      expect(sendListFiles).not.toHaveBeenCalled();
      expect(onChange).not.toHaveBeenCalled();
      expect(toast).toHaveBeenCalledWith({
        title: "Failed",
        description: "Permission denied",
      });
    });

    test("does not update or refresh after a failed delete", async () => {
      sendDeleteFileOrFolder.mockResolvedValueOnce({
        success: false,
        message: "Permission denied",
      });

      await tree.delete(PRIMARY_FILE_ID);

      expect(sendListFiles).not.toHaveBeenCalled();
      expect(onChange).not.toHaveBeenCalled();
      expect(toast).toHaveBeenCalledWith({
        title: "Failed",
        description: "Permission denied",
      });
    });

    test("does not update or refresh after a failed move", async () => {
      sendRenameFileOrFolder.mockResolvedValueOnce({
        success: false,
        message: "Permission denied",
      });

      await tree.move([PRIMARY_FILE_ID], EXTERNAL_ROOT_ID);

      expect(sendListFiles).not.toHaveBeenCalled();
      expect(onChange).not.toHaveBeenCalled();
      expect(toast).toHaveBeenCalledWith({
        title: "Failed",
        description: "Permission denied",
      });
    });
  });

  test("moves files across roots and refreshes both parents", async () => {
    await tree.expand(PRIMARY_ROOT_ID);
    sendListFiles.mockClear();

    await tree.move([PRIMARY_FILE_ID], EXTERNAL_ROOT_ID);

    expect(sendRenameFileOrFolder).toHaveBeenCalledWith({
      path: "/root/file1",
      newPath: "/external/file1",
    });
    expect(sendListFiles).toHaveBeenCalledWith({ path: "/root" });
    expect(sendListFiles).toHaveBeenCalledWith({ path: "/external" });
  });

  test("refreshes configured roots when every node is collapsed", async () => {
    await tree.refreshAll([]);
    expect(sendListFiles).toHaveBeenCalledWith({ path: "/root" });
    expect(sendListFiles).toHaveBeenCalledWith({ path: "/external" });
  });

  test("refreshes supplied open folders in addition to configured roots", async () => {
    await tree.expand(PRIMARY_ROOT_ID);
    sendListFiles.mockClear();

    await tree.refreshAll([fileTreeNodeId("/root", "/root/folder1")]);

    expect(sendListFiles).toHaveBeenCalledWith({ path: "/root" });
    expect(sendListFiles).toHaveBeenCalledWith({ path: "/external" });
    expect(sendListFiles).toHaveBeenCalledWith({ path: "/root/folder1" });
  });

  test("keeps existing children when a refresh fails", async () => {
    await tree.expand(PRIMARY_ROOT_ID);
    const beforeRefresh = onChange.mock.calls.at(-1)?.[0];
    sendListFiles.mockRejectedValueOnce(new Error("Network error"));

    await tree.refreshPath("/root" as FilePath);

    expect(onChange.mock.calls.at(-1)?.[0]).toEqual(beforeRefresh);
  });

  test("namespaces duplicate paths under overlapping roots", async () => {
    getRoots.mockResolvedValueOnce({
      roots: [
        { path: "/repo", name: "repo", isPrimary: true },
        { path: "/repo/data", name: "Data", isPrimary: false },
      ],
    });
    sendListFiles.mockImplementation(async ({ path }: { path: string }) => ({
      root: path,
      files:
        path === "/repo"
          ? [
              {
                id: "/repo/data",
                name: "data",
                path: "/repo/data",
                isDirectory: true,
                isMarimoFile: false,
                children: [],
              },
            ]
          : [
              {
                id: "/repo/data/file.csv",
                name: "file.csv",
                path: "/repo/data/file.csv",
                isDirectory: false,
                isMarimoFile: false,
                children: [],
              },
            ],
    }));
    const overlapOnChange = vi.fn();
    const overlapTree = new RequestingTree({
      getRoots,
      listFiles: sendListFiles,
      createFileOrFolder: sendCreateFileOrFolder,
      deleteFileOrFolder: sendDeleteFileOrFolder,
      copyFileOrFolder: sendCopyFileOrFolder,
      renameFileOrFolder: sendRenameFileOrFolder,
    });
    await overlapTree.initialize(overlapOnChange);

    const primaryRootId = fileTreeNodeId("/repo", "/repo");
    const nestedDirectoryId = fileTreeNodeId("/repo", "/repo/data");
    const additionalRootId = fileTreeNodeId("/repo/data", "/repo/data");
    expect(nestedDirectoryId).not.toBe(additionalRootId);

    await overlapTree.expand(primaryRootId);
    await overlapTree.expand(nestedDirectoryId);
    await overlapTree.expand(additionalRootId);

    const roots = overlapOnChange.mock.calls.at(-1)?.[0];
    expect(roots[0].children[0].id).toBe(nestedDirectoryId);
    expect(roots[1].id).toBe(additionalRootId);
    expect(roots[0].children[0].children[0].id).toBe(
      fileTreeNodeId("/repo", "/repo/data/file.csv"),
    );
    expect(roots[1].children[0].id).toBe(
      fileTreeNodeId("/repo/data", "/repo/data/file.csv"),
    );
    expect(
      overlapTree.getPrimaryRelativePath("/repo/data/file.csv" as FilePath),
    ).toBe("data/file.csv");
    expect(
      overlapTree.getDisplayPath(
        "/repo/data/file.csv" as FilePath,
        primaryRootId,
      ),
    ).toBe("data/file.csv");
    expect(
      overlapTree.getDisplayPath(
        "/repo/data/file.csv" as FilePath,
        additionalRootId,
      ),
    ).toBe("Data/file.csv");

    sendDeleteFileOrFolder.mockClear();
    await overlapTree.delete(nestedDirectoryId);
    expect(sendDeleteFileOrFolder).not.toHaveBeenCalled();
    expect(toast).toHaveBeenCalledWith(
      expect.objectContaining({
        description:
          "File browser roots and their parent folders cannot be modified",
      }),
    );
  });

  describe("primary-root paths", () => {
    test("returns relative paths only inside the primary root", () => {
      expect(tree.getPrimaryRelativePath("/root/src/file.py" as FilePath)).toBe(
        "src/file.py",
      );
      expect(
        tree.getPrimaryRelativePath("/rooted/file.py" as FilePath),
      ).toBeNull();
      expect(
        tree.getPrimaryRelativePath("/external/file.py" as FilePath),
      ).toBeNull();
    });

    test("supports Windows path boundaries case-insensitively", async () => {
      getRoots.mockResolvedValueOnce({
        roots: [
          {
            path: "C:\\Users\\Test\\Project",
            name: "Project",
            isPrimary: true,
          },
          {
            path: "D:\\Shared",
            name: "Shared",
            isPrimary: false,
          },
        ],
      });
      const windowsTree = new RequestingTree({
        getRoots,
        listFiles: sendListFiles,
        createFileOrFolder: sendCreateFileOrFolder,
        deleteFileOrFolder: sendDeleteFileOrFolder,
        copyFileOrFolder: sendCopyFileOrFolder,
        renameFileOrFolder: sendRenameFileOrFolder,
      });
      await windowsTree.initialize(vi.fn());

      expect(
        windowsTree.getPrimaryRelativePath(
          "c:\\users\\test\\project\\src\\file.py" as FilePath,
        ),
      ).toBe("src\\file.py");
      expect(
        windowsTree.getPrimaryRelativePath(
          "C:\\Users\\Test\\Project-old\\file.py" as FilePath,
        ),
      ).toBeNull();
      expect(
        windowsTree.getDisplayPath(
          "C:\\Users\\Test\\Project\\src\\file.py" as FilePath,
          fileTreeNodeId(
            "C:\\Users\\Test\\Project",
            "C:\\Users\\Test\\Project",
          ),
        ),
      ).toBe("src/file.py");
      expect(
        windowsTree.getDisplayPath(
          "D:\\Shared\\data\\file.csv" as FilePath,
          fileTreeNodeId("D:\\Shared", "D:\\Shared"),
        ),
      ).toBe("Shared/data/file.csv");
    });

    test("uses configured names in root-qualified display paths", () => {
      expect(tree.getDisplayPath("/root/data.csv" as FilePath)).toBe(
        "data.csv",
      );
      expect(tree.getDisplayPath("/external/data.csv" as FilePath)).toBe(
        "/external/data.csv",
      );
      expect(
        tree.getDisplayPath("/external/data.csv" as FilePath, EXTERNAL_ROOT_ID),
      ).toBe("Shared/data.csv");
      expect(
        tree.getDisplayPath("/external" as FilePath, EXTERNAL_ROOT_ID),
      ).toBe("Shared");
    });
  });
});
