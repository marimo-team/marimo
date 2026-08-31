/* Copyright 2026 Marimo. All rights reserved. */

import { SimpleTree } from "react-arborist";
import { toast } from "@/components/ui/use-toast";
import type {
  EditRequests,
  FileInfo,
  FileRoot,
  FileUpdateResponse,
} from "@/core/network/types";
import { prettyError } from "@/utils/errors";
import { Functions } from "@/utils/functions";
import { type FilePath, PathBuilder } from "@/utils/paths";
import { mapWithConcurrency } from "@/utils/semaphore";

const FILE_OP_CONCURRENCY = 5;

export type FileTreeNode = Omit<FileInfo, "children"> & {
  children: FileTreeNode[];
  isRoot: boolean;
  rootPath: string;
  isPrimaryRoot: boolean;
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

  private roots: FileRoot[] = [];
  private onChange: (data: FileTreeNode[]) => void = Functions.NOOP;
  private path = new PathBuilder("/");

  initialize = async (
    onChange: (data: FileTreeNode[]) => void,
  ): Promise<void> => {
    this.onChange = onChange;
    if (this.delegate.data.length === 0) {
      try {
        const { roots } = await this.callbacks.getRoots();
        const primaryRoot = roots.find((root) => root.isPrimary);
        if (!primaryRoot) {
          throw new Error("File browser response is missing a primary root");
        }
        this.roots = roots;
        this.path = PathBuilder.guessDeliminator(primaryRoot.path);
        this.delegate = new SimpleTree(roots.map(toRootNode));
      } catch (error) {
        toast({
          title: "Failed",
          description: prettyError(error),
        });
      }
    }

    this.emitChange();
  };

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
    const path = node.data.path as FilePath;
    const parentPath = this.getParentPath(node.data);
    const newPath = joinPath(parentPath, newName);
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
    const path = node.data.path as FilePath;
    const parentPath = this.getParentPath(node.data);
    const newPath = joinPath(parentPath, name);
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

    const refreshPaths = new Set<string>([parent.data.path]);
    await mapWithConcurrency(fromIds, FILE_OP_CONCURRENCY, async (id) => {
      const node = this.getMutableNode(id, false);
      if (!node) {
        return;
      }
      const originalPath = node.data.path;
      const sourceParentPath = this.getParentPath(node.data);
      const newPath = joinPath(
        parent.data.path,
        this.path.basename(originalPath as FilePath),
      );
      const result = await this.callbacks
        .renameFileOrFolder({ path: originalPath, newPath })
        .then(handleFileResponse);
      if (result) {
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
      await this.refreshPath(parent.data.path as FilePath);
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
      await this.refreshPath(parent.data.path as FilePath);
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
    const paths = ids
      .map((id) => this.delegate.find(id)?.data.path)
      .filter((path): path is string => Boolean(path));
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
    return relativePath(path, primaryRoot.path);
  };

  public getPrimaryRootPath = (): FilePath => {
    return (this.getPrimaryRoot()?.path ?? "") as FilePath;
  };

  public getPrimaryRootId = (): string => {
    const path = this.getPrimaryRoot()?.path ?? "";
    return fileTreeNodeId(path, path);
  };

  public isPrimaryNode = (node: FileTreeNode): boolean => {
    return node.isPrimaryRoot;
  };

  public getDisplayPath = (path: FilePath): string => {
    const root = this.getRootForPath(path);
    if (!root) {
      return path;
    }
    const relative = relativePath(path, root.path);
    if (!relative) {
      return root.name;
    }
    return root.isPrimary ? relative : `${root.name}/${relative}`;
  };

  public isRootPath = (path: FilePath): boolean => {
    return this.roots.some((root) => pathsEqual(path, root.path));
  };

  private getPrimaryRoot(): FileRoot | undefined {
    return this.roots.find((root) => root.isPrimary);
  }

  private getRootForNode(node: FileTreeNode): FileRoot {
    return (
      this.roots.find((root) => pathsEqual(root.path, node.rootPath)) ??
      this.getPrimaryRoot() ?? {
        path: node.rootPath,
        name: node.rootPath,
        isPrimary: node.isPrimaryRoot,
      }
    );
  }

  private getRootForPath(path: FilePath): FileRoot | undefined {
    return this.roots
      .filter((root) => relativePath(path, root.path) !== null)
      .toSorted((left, right) => right.path.length - left.path.length)[0];
  }

  private getParentNode(parentId: string | null) {
    const resolvedId = parentId ?? this.getPrimaryRootId();
    const node = this.delegate.find(resolvedId);
    return node?.data.isDirectory ? node : null;
  }

  private getParentPath(node: FileTreeNode): FilePath {
    const parent = this.delegate.find(node.id)?.parent;
    return (parent?.data.path ?? node.rootPath) as FilePath;
  }

  private getMutableNode(id: string, showError = true) {
    const node = this.delegate.find(id);
    if (!node || node.data.isRoot) {
      if (showError) {
        toast({
          title: "Failed",
          description: node
            ? "File browser roots cannot be modified"
            : `Node with id ${id} not found in the tree`,
        });
      }
      return null;
    }
    return node;
  }

  private refreshPaths = async (paths: string[]): Promise<void> => {
    const uniquePaths = [...new Set(paths)];
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
    this.onChange(this.delegate.data);
  }
}

function toRootNode(root: FileRoot): FileTreeNode {
  return {
    id: fileTreeNodeId(root.path, root.path),
    path: root.path,
    name: root.name,
    isDirectory: true,
    isMarimoFile: false,
    children: [],
    isRoot: true,
    rootPath: root.path,
    isPrimaryRoot: root.isPrimary,
  };
}

function annotateFiles(files: FileInfo[], root: FileRoot): FileTreeNode[] {
  return files.map((file) => ({
    ...file,
    id: fileTreeNodeId(root.path, file.path),
    children: annotateFiles(file.children ?? [], root),
    isRoot: false,
    rootPath: root.path,
    isPrimaryRoot: root.isPrimary,
  }));
}

/** A stable, globally unique tree ID for a path as viewed from one root. */
export function fileTreeNodeId(rootPath: string, path: string): string {
  return `${encodeURIComponent(rootPath)}:${encodeURIComponent(path)}`;
}

function relativePath(path: string, root: string): FilePath | null {
  const windowsPath = /^[A-Za-z]:[/\\]/.test(root);
  const normalizeCase = (value: string) =>
    windowsPath ? value.toLocaleLowerCase() : value;
  const comparedPath = normalizeCase(path);
  const comparedRoot = normalizeCase(root);
  if (comparedPath === comparedRoot) {
    return "" as FilePath;
  }

  const delimiter = root.includes("\\") ? "\\" : "/";
  const rootWithDelimiter = root.endsWith(delimiter)
    ? root
    : `${root}${delimiter}`;
  const comparedPrefix = normalizeCase(rootWithDelimiter);
  if (!comparedPath.startsWith(comparedPrefix)) {
    return null;
  }
  return path.slice(rootWithDelimiter.length) as FilePath;
}

function pathsEqual(left: string, right: string): boolean {
  return relativePath(left, right) === ("" as FilePath);
}

function joinPath(parent: string, name: string): FilePath {
  const delimiter = parent.includes("\\") ? "\\" : "/";
  return `${parent}${parent.endsWith(delimiter) ? "" : delimiter}${name}` as FilePath;
}
