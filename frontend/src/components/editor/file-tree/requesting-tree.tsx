/* Copyright 2026 Marimo. All rights reserved. */

import { SimpleTree } from "react-arborist";
import { toast } from "@/components/ui/use-toast";
import type {
  EditRequests,
  FileInfo,
  FileRoot,
  FileUpdateResponse,
} from "@/core/network/types";
import { Functions } from "@/utils/functions";
import { invariant } from "@/utils/invariant";
import { type FilePath, PathBuilder, relativeFilePath } from "@/utils/paths";
import { mapWithConcurrency } from "@/utils/semaphore";

const FILE_OP_CONCURRENCY = 5;

type FileTreeRoot = Omit<FileRoot, "path"> & {
  path: FilePath;
};

export type FileTreeNode = Omit<FileInfo, "children" | "path"> & {
  path: FilePath;
  children: FileTreeNode[];
  isRoot: boolean;
  rootId: string;
};

/**
 * Normalized result of a file mutation: the server response when successful,
 * `null` when the server rejected the request and a toast was surfaced.
 */
export type FileOperationResult = FileUpdateResponse | null;

export function handleFileResponse(
  response: FileUpdateResponse,
): FileOperationResult {
  if (!response.success) {
    toast({
      title: "Failed",
      description: response.message,
    });
    return null;
  }
  return response;
}

export class RequestingTree {
  private delegate = new SimpleTree<FileTreeNode>([]);
  private readonly callbacks: {
    getRoots: EditRequests["getFileRoots"];
    listFiles: EditRequests["sendListFiles"];
    createFileOrFolder: EditRequests["sendCreateFileOrFolder"];
    deleteFileOrFolder: EditRequests["sendDeleteFileOrFolder"];
    copyFileOrFolder: EditRequests["sendCopyFileOrFolder"];
    renameFileOrFolder: EditRequests["sendRenameFileOrFolder"];
  };

  constructor(callbacks: {
    getRoots: EditRequests["getFileRoots"];
    listFiles: EditRequests["sendListFiles"];
    createFileOrFolder: EditRequests["sendCreateFileOrFolder"];
    deleteFileOrFolder: EditRequests["sendDeleteFileOrFolder"];
    copyFileOrFolder: EditRequests["sendCopyFileOrFolder"];
    renameFileOrFolder: EditRequests["sendRenameFileOrFolder"];
  }) {
    this.callbacks = callbacks;
  }

  private roots: FileTreeRoot[] = [];
  private rootsById = new Map<string, FileTreeRoot>();
  private initialization: Promise<void> | null = null;
  private initialized = false;
  private onChange: (data: FileTreeNode[]) => void = Functions.NOOP;
  private path = new PathBuilder("/");

  initialize = async (
    onChange: (data: FileTreeNode[]) => void,
  ): Promise<void> => {
    this.onChange = onChange;
    if (this.initialized) {
      this.emitChange();
      return;
    }

    this.initialization ??= this.loadInitialData();
    try {
      await this.initialization;
      this.initialized = true;
    } finally {
      this.initialization = null;
    }
    this.emitChange();
  };

  private async loadInitialData(): Promise<void> {
    const response = await this.callbacks.getRoots();
    const roots = response.roots.map(toFileTreeRoot);
    const primaryRoot = roots.find((root) => root.isPrimary);
    if (!primaryRoot) {
      throw new Error("File browser response is missing a primary root");
    }

    const delegate = new SimpleTree(roots.map(toRootNode));
    if (roots.length === 1) {
      const data = await this.callbacks.listFiles({ path: primaryRoot.path });
      delegate.update({
        id: fileTreeNodeId(primaryRoot.path, primaryRoot.path),
        changes: { children: annotateFiles(data.files, primaryRoot) },
      });
    }

    this.roots = roots;
    this.rootsById = new Map(roots.map((root) => [rootId(root), root]));
    this.path = PathBuilder.guessDeliminator(primaryRoot.path);
    this.delegate = delegate;
  }

  async expand(id: string): Promise<boolean> {
    const node = this.delegate.find(id);
    if (!node?.data.isDirectory) {
      return false;
    }

    if (node.children && node.children.length > 0) {
      return true;
    }

    const data = await this.callbacks.listFiles({ path: node.data.path });
    this.delegate.update({
      id,
      changes: {
        children: annotateFiles(data.files, this.getRootForNode(node.data)),
      },
    });
    this.emitChange();
    return true;
  }

  async copy(id: string, newName: string): Promise<void> {
    const node = this.getMutableNode(id);
    if (!node) {
      return;
    }
    const path = node.data.path;
    const parentPath = this.getParentPath(node.data);
    const newPath = this.path.join(parentPath, newName);
    const result = await this.callbacks
      .copyFileOrFolder({ path, newPath })
      .then(handleFileResponse);
    if (result) {
      await this.refreshPath(parentPath);
    }
  }

  async rename(id: string, name: string): Promise<void> {
    const node = this.getMutableNode(id);
    if (!node) {
      return;
    }
    const path = node.data.path;
    const parentPath = this.getParentPath(node.data);
    const newPath = this.path.join(parentPath, name);
    const result = await this.callbacks
      .renameFileOrFolder({ path, newPath })
      .then(handleFileResponse);
    if (result) {
      await this.refreshPath(parentPath);
    }
  }

  async move(fromIds: string[], parentId: string | null): Promise<void> {
    const targetParentId = parentId ?? this.getPrimaryRootId();
    const parent = this.delegate.find(targetParentId);
    if (!parent?.data.isDirectory) {
      return;
    }

    const refreshPaths = new Set<FilePath>();
    await mapWithConcurrency(fromIds, FILE_OP_CONCURRENCY, async (id) => {
      const node = this.getMutableNode(id, false);
      if (!node) {
        return;
      }
      const originalPath = node.data.path;
      const sourceParentPath = this.getParentPath(node.data);
      const newPath = this.path.join(
        parent.data.path,
        this.path.basename(originalPath),
      );
      const result = await this.callbacks
        .renameFileOrFolder({ path: originalPath, newPath })
        .then(handleFileResponse);
      if (result) {
        refreshPaths.add(parent.data.path);
        refreshPaths.add(sourceParentPath);
      }
    });

    await this.refreshPaths([...refreshPaths]);
  }

  async createFile({
    name,
    parentId,
    type = "file",
  }: {
    name: string;
    parentId: string | null;
    type?: "file" | "notebook";
  }): Promise<void> {
    const parent = this.getParentNode(parentId);
    if (!parent) {
      return;
    }
    const result = await this.callbacks
      .createFileOrFolder({
        path: parent.data.path,
        type,
        name,
      })
      .then(handleFileResponse);
    if (result) {
      await this.refreshPath(parent.data.path);
    }
  }

  async createFolder(name: string, parentId: string | null): Promise<void> {
    const parent = this.getParentNode(parentId);
    if (!parent) {
      return;
    }
    const result = await this.callbacks
      .createFileOrFolder({
        path: parent.data.path,
        type: "directory",
        name,
      })
      .then(handleFileResponse);
    if (result) {
      await this.refreshPath(parent.data.path);
    }
  }

  async delete(id: string): Promise<void> {
    const node = this.getMutableNode(id);
    if (!node) {
      return;
    }
    const parentPath = this.getParentPath(node.data);
    const result = await this.callbacks
      .deleteFileOrFolder({ path: node.data.path })
      .then(handleFileResponse);
    if (result) {
      await this.refreshPath(parentPath);
    }
  }

  refreshAll = async (ids: string[]): Promise<void> => {
    const paths = [
      ...this.roots.map((root) => root.path),
      ...ids
        .map((id) => this.delegate.find(id)?.data.path)
        .filter((path): path is FilePath => Boolean(path)),
    ];
    await this.refreshPaths(paths);
  };

  refreshPath = async (path: FilePath): Promise<void> => {
    await this.refreshPaths([path]);
  };

  public getPrimaryRelativePath = (path: FilePath): FilePath | null => {
    const primaryRoot = this.getPrimaryRoot();
    if (!primaryRoot) {
      return null;
    }
    return relativeFilePath(path, primaryRoot.path);
  };

  public getPrimaryRootPath = (): FilePath => {
    return this.getPrimaryRoot()?.path ?? ("" as FilePath);
  };

  public getPrimaryRootId = (): string => {
    const path = this.getPrimaryRoot()?.path ?? "";
    return fileTreeNodeId(path, path);
  };

  public getDisplayPath = (
    path: FilePath,
    rootId = this.getPrimaryRootId(),
  ): string => {
    const root = this.rootsById.get(rootId);
    if (!root) {
      return path;
    }
    const relative = relativeFilePath(path, root.path);
    if (relative === null) {
      return path;
    }
    if (!relative) {
      return root.name;
    }
    const displayPath = relative.replaceAll("\\", "/");
    return root.isPrimary ? displayPath : `${root.name}/${displayPath}`;
  };

  public isProtectedFromMutation = (path: FilePath): boolean => {
    return this.roots.some(
      (root) => relativeFilePath(root.path, path) !== null,
    );
  };

  private getPrimaryRoot(): FileTreeRoot | undefined {
    return this.roots.find((root) => root.isPrimary);
  }

  private getRootForNode(node: FileTreeNode): FileTreeRoot {
    const root = this.rootsById.get(node.rootId);
    invariant(root, `No file browser root found for node ${node.id}`);
    return root;
  }

  private getParentNode(parentId: string | null) {
    const resolvedId = parentId ?? this.getPrimaryRootId();
    const node = this.delegate.find(resolvedId);
    return node?.data.isDirectory ? node : null;
  }

  private getParentPath(node: FileTreeNode): FilePath {
    const parent = this.delegate.find(node.id)?.parent;
    return parent?.data.path ?? this.getRootForNode(node).path;
  }

  private getMutableNode(id: string, showError = true) {
    const node = this.delegate.find(id);
    // Mutating a configured root or one of its ancestors would invalidate the
    // browser configuration, including through an overlapping occurrence.
    const isProtected = node
      ? this.isProtectedFromMutation(node.data.path)
      : false;
    if (!node || node.data.isRoot || isProtected) {
      if (showError) {
        toast({
          title: "Failed",
          description: node
            ? "File browser roots and their parent folders cannot be modified"
            : `Node with id ${id} not found in the tree`,
        });
      }
      return null;
    }
    return node;
  }

  private refreshPaths = async (paths: FilePath[]): Promise<void> => {
    const uniquePaths = [...new Set(paths)];
    if (uniquePaths.length === 0) {
      return;
    }
    const results = await mapWithConcurrency(
      uniquePaths,
      FILE_OP_CONCURRENCY,
      (path) => this.callbacks.listFiles({ path }).catch(() => null),
    );

    for (const [index, path] of uniquePaths.entries()) {
      const result = results[index];
      if (!result) {
        continue;
      }
      // The same absolute path may appear below multiple overlapping roots.
      // Refresh every occurrence, while keeping each occurrence in its own ID
      // namespace and preserving its root metadata.
      for (const root of this.roots) {
        const node = this.delegate.find(fileTreeNodeId(root.path, path));
        if (!node?.data.isDirectory) {
          continue;
        }
        this.delegate.update({
          id: node.id,
          changes: {
            children: annotateFiles(result.files, root),
          },
        });
      }
    }
    this.emitChange();
  };

  private emitChange(): void {
    const data = this.delegate.data;
    this.onChange(this.roots.length === 1 ? (data[0]?.children ?? []) : data);
  }
}

function toFileTreeRoot(root: FileRoot): FileTreeRoot {
  return {
    ...root,
    path: root.path as FilePath,
  };
}

function toRootNode(root: FileTreeRoot): FileTreeNode {
  return {
    id: fileTreeNodeId(root.path, root.path),
    path: root.path,
    name: root.name,
    isDirectory: true,
    isMarimoFile: false,
    children: [],
    isRoot: true,
    rootId: rootId(root),
  };
}

function annotateFiles(files: FileInfo[], root: FileTreeRoot): FileTreeNode[] {
  return files.map((file) => ({
    ...file,
    path: file.path as FilePath,
    id: fileTreeNodeId(root.path, file.path),
    children: annotateFiles(file.children ?? [], root),
    isRoot: false,
    rootId: rootId(root),
  }));
}

/** A stable, globally unique tree ID for a path as viewed from one root. */
export function fileTreeNodeId(rootPath: string, path: string): string {
  return `${encodeURIComponent(rootPath)}:${encodeURIComponent(path)}`;
}

function rootId(root: FileTreeRoot): string {
  return fileTreeNodeId(root.path, root.path);
}
